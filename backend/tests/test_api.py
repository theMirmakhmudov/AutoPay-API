def test_api_unauthorized(client):
    response = client.post("/api/v1/payments/", json={"base_amount": 35000})
    # Our client fixture injects get_current_merchant, so let's clear it for an unauthorized test
    from autopay.app import app
    from autopay.core.security import get_current_merchant

    app.dependency_overrides.pop(get_current_merchant, None)

    response = client.post("/api/v1/payments/", json={"base_amount": 35000})
    assert response.status_code == 403


def test_create_and_check_payment(client, test_merchant):
    # Test merchant is automatically authenticated via the fixture overrides

    # 1. Create Payment
    resp1 = client.post("/api/v1/payments/", json={"base_amount": 35000})
    assert resp1.status_code == 200
    data = resp1.json()["data"]
    assert data["base_amount"] == 35000.0
    payment_id = data["payment_id"]

    # 2. Check Status
    resp2 = client.get(f"/api/v1/payments/status?payment_id={payment_id}")
    assert resp2.status_code == 200
    assert resp2.json()["data"]["status"] == "PENDING"

    # 3. Cancel Payment
    resp3 = client.post(f"/api/v1/payments/cancel?payment_id={payment_id}")
    assert resp3.status_code == 200
    assert resp3.json()["data"]["status"] == "CANCELLED"

    # 4. Check Status again
    resp4 = client.get(f"/api/v1/payments/status?payment_id={payment_id}")
    assert resp4.status_code == 200
    assert resp4.json()["data"]["status"] == "CANCELLED"


def test_webhook_unmatched(client, test_merchant):
    # This tests the Webhook endpoint that the Userbot triggers
    payload = {
        "message_id": 12345,
        "chat_username": "clickuz",
        "raw_text": "🎉 To'ldirish\n➕ 99.000,00 UZS\n💳 VISA *4183",
        "date_received": "2026-06-03T10:00:00Z",
    }

    resp = client.post(f"/api/v1/webhooks/telegram?merchant_id={test_merchant.id}", json=payload)

    assert resp.status_code == 200
    assert resp.json()["data"]["matched"] is False
    assert resp.json()["data"]["amount"] == 99000.0


def test_webhook_matched(client, test_merchant):
    # 1. Create a payment intent for 35000
    resp_create = client.post("/api/v1/payments/", json={"base_amount": 35000})
    payment_id = resp_create.json()["data"]["payment_id"]

    # 2. Simulate Telegram message arriving for exactly 35000
    payload = {
        "message_id": 99999,
        "chat_username": "clickuz",
        "raw_text": "🎉 To'ldirish\n➕ 35.000,00 UZS\n💳 VISA *4183",
        "date_received": "2026-06-03T10:05:00Z",
    }

    resp_wh = client.post(f"/api/v1/webhooks/telegram?merchant_id={test_merchant.id}", json=payload)

    assert resp_wh.status_code == 200
    assert resp_wh.json()["data"]["matched"] is True

    # 3. Status should now be PAID
    resp_status = client.get(f"/api/v1/payments/status?payment_id={payment_id}")
    assert resp_status.json()["data"]["status"] == "PAID"


def test_check_status_not_found(client, test_merchant):
    resp = client.get("/api/v1/payments/status?payment_id=nonexistent")
    assert resp.status_code == 404


def test_cancel_payment_not_found(client, test_merchant):
    resp = client.post("/api/v1/payments/cancel?payment_id=nonexistent")
    assert resp.status_code == 404


def test_cancel_payment_not_pending(client, test_merchant):
    # Create payment
    resp1 = client.post("/api/v1/payments/", json={"base_amount": 35000})
    payment_id = resp1.json()["data"]["payment_id"]

    # Cancel once (should succeed)
    resp2 = client.post(f"/api/v1/payments/cancel?payment_id={payment_id}")
    assert resp2.status_code == 200

    # Cancel twice (should return error because it's no longer PENDING)
    resp3 = client.post(f"/api/v1/payments/cancel?payment_id={payment_id}")
    assert resp3.status_code == 200
    assert resp3.json()["success"] is False


def test_websocket_payment_status_disconnect(client):
    # Instead of full mock asserting, just ensure it handles disconnect gracefully
    with client.websocket_connect("/api/v1/payments/ws/12345") as websocket:
        websocket.close()


def test_webhook_merchant_mismatch(client, test_merchant):
    payload = {
        "message_id": 12345,
        "chat_username": "clickuz",
        "raw_text": "🎉 To'ldirish\n➕ 99.000,00 UZS\n💳 VISA *4183",
        "date_received": "2026-06-03T10:00:00Z",
    }
    resp = client.post("/api/v1/webhooks/telegram?merchant_id=wrong_id", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert resp.json()["error_code"] == "MERCHANT_MISMATCH"


def test_webhook_duplicate(client, test_merchant):
    payload = {
        "message_id": 77777,
        "chat_username": "clickuz",
        "raw_text": "🎉 To'ldirish\n➕ 99.000,00 UZS\n💳 VISA *4183",
        "date_received": "2026-06-03T10:00:00Z",
    }
    # First request
    client.post(f"/api/v1/webhooks/telegram?merchant_id={test_merchant.id}", json=payload)
    # Second request with same message_id
    resp = client.post(f"/api/v1/webhooks/telegram?merchant_id={test_merchant.id}", json=payload)
    assert resp.status_code == 200
    assert resp.json()["message"] == "Duplicate — already processed"


def test_webhook_parse_error(client, test_merchant):
    payload = {
        "message_id": 88888,
        "chat_username": "unknown_bot",
        "raw_text": "some random text",
        "date_received": "2026-06-03T10:00:00Z",
    }
    resp = client.post(f"/api/v1/webhooks/telegram?merchant_id={test_merchant.id}", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert resp.json()["error_code"] == "PARSE_ERROR"


def test_root_health_check(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
