import asyncio

import asyncpg
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session

from autopay.core.config import settings
from autopay.core.database import get_db
from autopay.core.rate_limit import limiter
from autopay.core.security import get_current_merchant
from autopay.models.payment import Merchant
from autopay.repositories.payment_repo import PaymentRepository
from autopay.schemas.base import BaseResponse, create_error_response, create_success_response
from autopay.schemas.payload import (
    CreatePaymentRequest,
    CreatePaymentResponse,
    PaymentStatusResponse,
)
from autopay.services.payment_service import PaymentService

router = APIRouter()


@router.post(
    "/",
    response_model=BaseResponse[CreatePaymentResponse],
    summary="Create a new payment",
    description="Creates a new payment intent. Returns the exact amount the user must transfer and the payment_id to poll for status.",
)
@limiter.limit("5/second")
def create_payment(
    request: Request,
    payload: CreatePaymentRequest,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant),
):
    service = PaymentService(db)
    response = service.create_payment_intent(merchant.id, payload)
    return create_success_response(data=response, message="Payment created")


@router.get(
    "/status",
    response_model=BaseResponse[PaymentStatusResponse],
    summary="Check payment status",
    description="Poll this endpoint to check if the payment has been received. Status: PENDING | PAID | EXPIRED | CANCELLED",
)
@limiter.limit("5/second")
def check_status(
    request: Request,
    payment_id: str = Query(..., description="The payment_id returned from POST /payments"),
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant),
):
    repo = PaymentRepository(db)
    payment = repo.get_intent(payment_id, merchant.id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    return create_success_response(
        data=PaymentStatusResponse(
            payment_id=payment.id,
            status=payment.status,
            expected_amount=payment.expected_amount,
            expires_at=payment.expires_at,
        ),
        message="Status fetched",
    )


@router.post(
    "/cancel",
    response_model=BaseResponse[dict],
    summary="Cancel a payment",
    description="Cancels a PENDING payment and frees up the locked amount.",
)
@limiter.limit("5/second")
def cancel_payment(
    request: Request,
    payment_id: str = Query(..., description="The payment_id to cancel"),
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(get_current_merchant),
):
    repo = PaymentRepository(db)
    payment = repo.get_intent(payment_id, merchant.id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.status != "PENDING":
        return create_error_response(
            message=f"Cannot cancel a payment with status '{payment.status}'"
        )

    payment.status = "CANCELLED"
    db.commit()
    return create_success_response(
        data={"payment_id": payment_id, "status": "CANCELLED"}, message="Payment cancelled"
    )


@router.websocket("/ws/{payment_id}")
async def websocket_payment_status(websocket: WebSocket, payment_id: str):
    """
    Real-time WebSocket endpoint that listens to PostgreSQL NOTIFY
    and instantly pushes the PAID status to the frontend.
    """
    await websocket.accept()

    conn = None
    try:
        # Use asyncpg for true async LISTEN/NOTIFY without blocking the event loop
        conn = await asyncpg.connect(settings.DATABASE_URL)
        queue = asyncio.Queue()

        def handle_notify(connection, pid, channel, payload):
            if payload == payment_id:
                queue.put_nowait(payload)

        await conn.add_listener("payment_updates", handle_notify)

        while True:
            # Race receiving a websocket message (to detect disconnects) vs receiving a postgres notification
            ws_task = asyncio.create_task(websocket.receive_text())
            q_task = asyncio.create_task(queue.get())

            done, pending = await asyncio.wait(
                [ws_task, q_task], return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            if q_task in done:
                # Payment was marked PAID in the database!
                await websocket.send_json({"payment_id": payment_id, "status": "PAID"})
                break

            if ws_task in done:
                # If client disconnected, this raises WebSocketDisconnect
                ws_task.result()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket Error: {e}")
    finally:
        if conn:
            try:
                await conn.remove_listener("payment_updates", handle_notify)
                await conn.close()
            except Exception:
                pass
