from fastapi import APIRouter, Depends, Query, status
from typing import List, Optional
from app.services.auth_service import get_current_user, RoleChecker, verify_client_access
from app.models.payment_model import RecordPayment, PaymentResponse
from app.services.payment_service import PaymentService

router = APIRouter()

allow_write = RoleChecker(["admin", "employee"])
allow_any = RoleChecker(["admin", "employee", "client"])


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def record_payment(
    payment_in: RecordPayment,
    current_user: dict = Depends(allow_write)
):
    """
    Record a payment against an invoice.
    - Validates invoice exists and belongs to the specified client.
    - Rejects payments exceeding the invoice balance_due.
    - Auto-updates invoice amount_paid, balance_due, and payment_status.
    Requires 'admin' or 'employee' role.
    """
    payment = await PaymentService.record_payment(payment_in, current_user["user_id"])
    return payment


@router.get("/{id}", response_model=PaymentResponse)
async def get_payment(
    id: str,
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve a specific payment by ID.
    Clients can only view payments for their own invoices.
    """
    payment = await PaymentService.get_payment(id)
    verify_client_access(current_user, payment["client_id"])
    return payment


@router.post("/{id}/verify", response_model=PaymentResponse)
async def verify_payment(
    id: str,
    current_user: dict = Depends(allow_write)
):
    """
    Verify a pending payment.
    Only 'pending' payments can be verified.
    Requires 'admin' or 'employee' role.
    """
    payment = await PaymentService.verify_payment(id, current_user["user_id"])
    return payment


@router.get("/invoice/{invoice_id}/history", response_model=List[PaymentResponse])
async def get_payment_history_by_invoice(
    invoice_id: str,
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve all payments for a specific invoice, ordered by payment_date descending.
    """
    payments = await PaymentService.get_payment_history_by_invoice(invoice_id)
    return payments


@router.get("/client/{client_id}/history", response_model=List[PaymentResponse])
async def get_payment_history_by_client(
    client_id: str,
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve all payments for a specific client, ordered by payment_date descending.
    Clients can only view their own payment history.
    """
    verify_client_access(current_user, client_id)
    payments = await PaymentService.get_payment_history_by_client(client_id)
    return payments


@router.get("/outstanding/balances")
async def get_outstanding_balances(
    client_id: Optional[str] = Query(None, description="Optional client ID filter"),
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve all invoices with outstanding balances (balance_due > 0).
    Optionally filtered by client_id.
    """
    if current_user.get("role") == "client":
        # Clients can only see their own outstanding balances
        client_id = current_user.get("client_id")

    balances = await PaymentService.get_outstanding_balances(client_id)
    return {"outstanding_invoices": balances, "count": len(balances)}


@router.get("/overdue/invoices")
async def get_overdue_invoices(
    client_id: Optional[str] = Query(None, description="Optional client ID filter"),
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve all invoices that are past their due date with outstanding balance.
    """
    if current_user.get("role") == "client":
        client_id = current_user.get("client_id")

    overdue = await PaymentService.get_overdue_invoices(client_id)
    return {"overdue_invoices": overdue, "count": len(overdue)}
