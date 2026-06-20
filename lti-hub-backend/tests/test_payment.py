import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import HTTPException
from app.models.payment_model import RecordPayment, PaymentMethodEnum, PaymentStatusEnum
from app.services.payment_service import PaymentService

MOCK_CLIENT_ID = str(ObjectId())
MOCK_INVOICE_ID = str(ObjectId())
MOCK_PAYMENT_ID = str(ObjectId())


@pytest.mark.asyncio
async def test_record_payment_success():
    """Test successful payment recording and invoice update."""
    payment_in = RecordPayment(
        invoice_id=MOCK_INVOICE_ID,
        client_id=MOCK_CLIENT_ID,
        payment_amount=500.0,
        payment_method=PaymentMethodEnum.BANK_TRANSFER,
        reference_number="REF123"
    )

    mock_invoice = {
        "_id": ObjectId(MOCK_INVOICE_ID),
        "client_id": MOCK_CLIENT_ID,
        "payment_status": "sent",
        "balance_due": 1000.0,
        "amount_paid": 0.0,
        "grand_total": 1000.0
    }

    mock_inserted_id = ObjectId()
    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id=mock_inserted_id))

    with patch("app.services.payment_service.validate_client_exists", AsyncMock(return_value=True)), \
         patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=mock_invoice)), \
         patch("app.services.payment_service.get_payments_collection", return_value=mock_collection), \
         patch("app.services.invoice_service.InvoiceService.record_payment_on_invoice", AsyncMock()) as mock_invoice_update:

        result = await PaymentService.record_payment(payment_in, "employee_1")

        assert result["payment_amount"] == 500.0
        assert result["status"] == "pending"
        assert result["_id"] == mock_inserted_id
        mock_collection.insert_one.assert_called_once()
        mock_invoice_update.assert_called_once_with(MOCK_INVOICE_ID, 500.0)


@pytest.mark.asyncio
async def test_record_payment_wrong_client():
    """Test payment rejection if client ID doesn't match invoice client ID."""
    payment_in = RecordPayment(
        invoice_id=MOCK_INVOICE_ID,
        client_id=str(ObjectId()), # Different client
        payment_amount=500.0,
        payment_method=PaymentMethodEnum.BANK_TRANSFER
    )

    mock_invoice = {
        "_id": ObjectId(MOCK_INVOICE_ID),
        "client_id": MOCK_CLIENT_ID, # Original client
    }

    with patch("app.services.payment_service.validate_client_exists", AsyncMock(return_value=True)), \
         patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=mock_invoice)):

        with pytest.raises(HTTPException) as exc_info:
            await PaymentService.record_payment(payment_in, "employee_1")
        assert exc_info.value.status_code == 400
        assert "does not belong to client" in exc_info.value.detail


@pytest.mark.asyncio
async def test_record_payment_overpayment_rejected():
    """Test payment rejection if amount exceeds balance due."""
    payment_in = RecordPayment(
        invoice_id=MOCK_INVOICE_ID,
        client_id=MOCK_CLIENT_ID,
        payment_amount=1500.0, # Exceeds balance
        payment_method=PaymentMethodEnum.BANK_TRANSFER
    )

    mock_invoice = {
        "_id": ObjectId(MOCK_INVOICE_ID),
        "client_id": MOCK_CLIENT_ID,
        "payment_status": "sent",
        "balance_due": 1000.0
    }

    with patch("app.services.payment_service.validate_client_exists", AsyncMock(return_value=True)), \
         patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=mock_invoice)):

        with pytest.raises(HTTPException) as exc_info:
            await PaymentService.record_payment(payment_in, "employee_1")
        assert exc_info.value.status_code == 400
        assert "exceeds outstanding balance" in exc_info.value.detail


@pytest.mark.asyncio
async def test_record_payment_draft_rejected():
    """Test payment rejection on a draft invoice."""
    payment_in = RecordPayment(
        invoice_id=MOCK_INVOICE_ID,
        client_id=MOCK_CLIENT_ID,
        payment_amount=500.0,
        payment_method=PaymentMethodEnum.BANK_TRANSFER
    )

    mock_invoice = {
        "_id": ObjectId(MOCK_INVOICE_ID),
        "client_id": MOCK_CLIENT_ID,
        "payment_status": "draft", # Draft status
        "balance_due": 1000.0
    }

    with patch("app.services.payment_service.validate_client_exists", AsyncMock(return_value=True)), \
         patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=mock_invoice)):

        with pytest.raises(HTTPException) as exc_info:
            await PaymentService.record_payment(payment_in, "employee_1")
        assert exc_info.value.status_code == 400
        assert "Cannot record payment on a 'draft' invoice" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_payment():
    """Test verifying a pending payment."""
    pending_payment = {
        "_id": ObjectId(MOCK_PAYMENT_ID),
        "status": "pending"
    }

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()

    with patch("app.services.payment_service.PaymentService.get_payment", AsyncMock(return_value=pending_payment)), \
         patch("app.services.payment_service.get_payments_collection", return_value=mock_collection):

        await PaymentService.verify_payment(MOCK_PAYMENT_ID, "admin_user")

        call_args = mock_collection.update_one.call_args[0][1]
        assert call_args["$set"]["status"] == "verified"
        assert call_args["$set"]["verified_by"] == "admin_user"


@pytest.mark.asyncio
async def test_verify_payment_already_verified():
    """Test verifying a payment that is not pending."""
    verified_payment = {
        "_id": ObjectId(MOCK_PAYMENT_ID),
        "status": "verified"
    }

    with patch("app.services.payment_service.PaymentService.get_payment", AsyncMock(return_value=verified_payment)):
        with pytest.raises(HTTPException) as exc_info:
            await PaymentService.verify_payment(MOCK_PAYMENT_ID, "admin_user")
        assert exc_info.value.status_code == 400
        assert "only 'pending' payments can be verified" in exc_info.value.detail
