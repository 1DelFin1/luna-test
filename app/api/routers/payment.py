from uuid import UUID

from fastapi import APIRouter, Header, status

from app.api.deps import ApiKeyDep, SessionDep
from app.schemas import CreatePaymentRequest, PaymentCreatedResponse, PaymentDetailResponse
from app.services import PaymentService

payment_router = APIRouter(tags=["Payment"], prefix="/payments", dependencies=[ApiKeyDep])


@payment_router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=PaymentCreatedResponse)
async def create_payment_handler(
    body: CreatePaymentRequest,
    session: SessionDep,
    idempotency_key: UUID = Header(alias="Idempotency-Key"),
) -> PaymentCreatedResponse:
    return await PaymentService.create_payment(session, body, idempotency_key)


@payment_router.get("/{payment_id}", response_model=PaymentDetailResponse)
async def get_payment_handler(payment_id: UUID, session: SessionDep) -> PaymentDetailResponse:
    return await PaymentService.get_payment(session, payment_id)
