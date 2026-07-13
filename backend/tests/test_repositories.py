from datetime import datetime, timedelta, timezone

from autopay.models.payment import ProcessedPayment
from autopay.repositories.payment_repo import PaymentRepository


def test_merchant_by_api_key(db_session, test_merchant):
    repo = PaymentRepository(db_session)
    merchant = repo.get_merchant_by_api_key(test_merchant.api_key_hash)
    assert merchant is not None
    assert merchant.id == test_merchant.id


def test_update_merchant_webhook(db_session, test_merchant):
    repo = PaymentRepository(db_session)
    # Exists
    m1 = repo.update_merchant_webhook(test_merchant.id, "https://example.com/wh")
    assert m1.webhook_url == "https://example.com/wh"
    # Doesn't exist
    m2 = repo.update_merchant_webhook("does_not_exist", "https://example.com/wh")
    assert m2 is None


def test_mark_intent_paid_sqlite_fallback(db_session, test_merchant):
    # test that NOTIFY fails gracefully on sqlite
    repo = PaymentRepository(db_session)
    intent = repo.create_intent(
        merchant_id=test_merchant.id,
        base_amount_tiyins=1000,
        expected_amount_tiyins=1000,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    repo.mark_intent_paid(intent, payment_id=999)
    assert intent.status == "PAID"
    assert intent.matched_payment_id == 999


def test_expire_old_intents(db_session, test_merchant):
    repo = PaymentRepository(db_session)
    # Create one expired, one active
    intent_expired = repo.create_intent(
        merchant_id=test_merchant.id,
        base_amount_tiyins=1000,
        expected_amount_tiyins=1000,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),  # past
    )
    intent_active = repo.create_intent(
        merchant_id=test_merchant.id,
        base_amount_tiyins=2000,
        expected_amount_tiyins=2000,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),  # future
    )

    expired_count = repo.expire_old_intents()
    assert expired_count == 1

    db_session.refresh(intent_expired)
    db_session.refresh(intent_active)
    assert intent_expired.status == "EXPIRED"
    assert intent_active.status == "PENDING"


def test_payment_exists(db_session, test_merchant):
    repo = PaymentRepository(db_session)
    assert not repo.payment_exists(1, "test_chat", test_merchant.id)

    # Save a processed payment
    payment = ProcessedPayment(
        merchant_id=test_merchant.id,
        message_id=1,
        chat_username="test_chat",
        amount_tiyins=1000,
        card_type="VISA",
        source="test",
        date_received=datetime.now(timezone.utc),
    )
    db_session.add(payment)
    db_session.commit()

    # Now it exists
    assert repo.payment_exists(1, "test_chat", test_merchant.id)


def test_save_unparsed_message(db_session, test_merchant):
    repo = PaymentRepository(db_session)
    unparsed = repo.save_unparsed_message(
        message_id=2,
        chat_username="test_chat",
        raw_text="raw_text",
        error_reason="parse error",
        merchant_id=test_merchant.id,
    )
    assert unparsed.message_id == 2
    # Check that payment_exists returns True for unparsed as well
    assert repo.payment_exists(2, "test_chat", test_merchant.id)
