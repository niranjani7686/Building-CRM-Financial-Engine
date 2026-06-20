import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import HTTPException
from app.models.invoice_model import InvoiceCreate, InvoiceUpdate, PaymentStatus
from app.services.invoice_service import InvoiceService

MOCK_CLIENT_ID = str(ObjectId())
MOCK_INVOICE_ID = str(ObjectId())


@pytest.mark.asyncio
async def test_create_invoice():
    """Test invoice creation: auto-numbering, server-side grand_total recalculation, balance_due initialization."""
    invoice_in = InvoiceCreate(
        client_id=MOCK_CLIENT_ID,
        subtotal=1000.0,
        tax_amount=180.0,
        grand_total=9999.0  # Should be IGNORED by server
    )

    mock_inserted_id = ObjectId()
    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id=mock_inserted_id))

    with patch("app.services.invoice_service.validate_client_exists", AsyncMock(return_value=True)), \
         patch("app.services.invoice_service.get_invoices_collection", return_value=mock_collection), \
         patch("app.services.invoice_service.generate_invoice_number", AsyncMock(return_value="INV-20260619-001")):

        result = await InvoiceService.create_invoice(invoice_in, "employee_1")

        # Server recalculates grand_total = subtotal + tax_amount, ignoring client-supplied value
        assert result["grand_total"] == 1180.0  # NOT 9999.0
        assert result["balance_due"] == 1180.0
        assert result["amount_paid"] == 0.0
        assert result["payment_status"] == "draft"
        assert result["invoice_number"] == "INV-20260619-001"
        assert result["_id"] == mock_inserted_id
        mock_collection.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_update_invoice_draft_recalculates():
    """Test updating a draft invoice recalculates grand_total and balance_due server-side."""
    invoice_doc = {
        "_id": ObjectId(MOCK_INVOICE_ID),
        "client_id": MOCK_CLIENT_ID,
        "invoice_number": "INV-20260619-001",
        "subtotal": 1000.0,
        "tax_amount": 180.0,
        "grand_total": 1180.0,
        "amount_paid": 0.0,
        "balance_due": 1180.0,
        "due_date": datetime.now(timezone.utc) + timedelta(days=30),
        "payment_status": "draft",
        "created_at": datetime.now(timezone.utc)
    }

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()

    update_in = InvoiceUpdate(subtotal=2000.0)  # Change subtotal, tax stays

    with patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=invoice_doc)), \
         patch("app.services.invoice_service.get_invoices_collection", return_value=mock_collection):

        await InvoiceService.update_invoice(MOCK_INVOICE_ID, update_in, "employee_1")

        call_args = mock_collection.update_one.call_args[0][1]
        # New grand_total = 2000 + 180 = 2180
        assert call_args["$set"]["subtotal"] == 2000.0
        assert call_args["$set"]["grand_total"] == 2180.0
        assert call_args["$set"]["balance_due"] == 2180.0


@pytest.mark.asyncio
async def test_update_invoice_blocked_when_sent():
    """Test that editing a 'sent' invoice is blocked."""
    sent_invoice = {
        "_id": ObjectId(MOCK_INVOICE_ID),
        "client_id": MOCK_CLIENT_ID,
        "payment_status": "sent",
        "subtotal": 1000.0,
        "tax_amount": 180.0,
        "grand_total": 1180.0,
        "amount_paid": 0.0,
        "balance_due": 1180.0,
        "due_date": datetime.now(timezone.utc) + timedelta(days=30),
        "created_at": datetime.now(timezone.utc)
    }

    with patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=sent_invoice)):
        with pytest.raises(HTTPException) as exc_info:
            await InvoiceService.update_invoice(MOCK_INVOICE_ID, InvoiceUpdate(subtotal=5000.0), "user")
        assert exc_info.value.status_code == 400
        assert "Must be 'draft'" in exc_info.value.detail


@pytest.mark.asyncio
async def test_invoice_status_transitions():
    """Test invoice status transition rules: valid and invalid paths."""
    base_doc = {
        "_id": ObjectId(MOCK_INVOICE_ID),
        "client_id": MOCK_CLIENT_ID,
        "payment_status": "draft",
        "due_date": datetime.now(timezone.utc) + timedelta(days=30)
    }

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()

    # Valid: draft -> sent
    with patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=base_doc)), \
         patch("app.services.invoice_service.get_invoices_collection", return_value=mock_collection):
        await InvoiceService.change_status(MOCK_INVOICE_ID, PaymentStatus.SENT, "user")
        mock_collection.update_one.assert_called_once()

    # Invalid: draft -> paid (must go through sent first)
    with patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=base_doc)):
        with pytest.raises(HTTPException) as exc_info:
            await InvoiceService.change_status(MOCK_INVOICE_ID, PaymentStatus.PAID, "user")
        assert exc_info.value.status_code == 400

    # Valid: sent -> partially_paid
    sent_doc = {**base_doc, "payment_status": "sent"}
    mock_collection.reset_mock()
    with patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=sent_doc)), \
         patch("app.services.invoice_service.get_invoices_collection", return_value=mock_collection):
        await InvoiceService.change_status(MOCK_INVOICE_ID, PaymentStatus.PARTIALLY_PAID, "user")
        mock_collection.update_one.assert_called_once()

    # Valid: partially_paid -> paid
    pp_doc = {**base_doc, "payment_status": "partially_paid"}
    mock_collection.reset_mock()
    with patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=pp_doc)), \
         patch("app.services.invoice_service.get_invoices_collection", return_value=mock_collection):
        await InvoiceService.change_status(MOCK_INVOICE_ID, PaymentStatus.PAID, "user")
        mock_collection.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_record_payment_on_invoice():
    """Test payment recording: partial payment, full payment, overpayment rejection."""
    sent_invoice = {
        "_id": ObjectId(MOCK_INVOICE_ID),
        "client_id": MOCK_CLIENT_ID,
        "payment_status": "sent",
        "grand_total": 1000.0,
        "amount_paid": 0.0,
        "balance_due": 1000.0,
        "due_date": datetime.now(timezone.utc) + timedelta(days=30)
    }

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()

    # Partial payment: pay 400 of 1000
    with patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=sent_invoice)), \
         patch("app.services.invoice_service.get_invoices_collection", return_value=mock_collection):

        await InvoiceService.record_payment_on_invoice(MOCK_INVOICE_ID, 400.0)

        call_args = mock_collection.update_one.call_args[0][1]
        assert call_args["$set"]["amount_paid"] == 400.0
        assert call_args["$set"]["balance_due"] == 600.0
        assert call_args["$set"]["payment_status"] == "partially_paid"

    # Full payment: pay remaining 600
    partial_invoice = {**sent_invoice, "amount_paid": 400.0, "balance_due": 600.0, "payment_status": "partially_paid"}
    mock_collection.reset_mock()
    with patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=partial_invoice)), \
         patch("app.services.invoice_service.get_invoices_collection", return_value=mock_collection):

        await InvoiceService.record_payment_on_invoice(MOCK_INVOICE_ID, 600.0)

        call_args = mock_collection.update_one.call_args[0][1]
        assert call_args["$set"]["amount_paid"] == 1000.0
        assert call_args["$set"]["balance_due"] == 0.0
        assert call_args["$set"]["payment_status"] == "paid"

    # Overpayment rejected
    with patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=sent_invoice)):
        with pytest.raises(HTTPException) as exc_info:
            await InvoiceService.record_payment_on_invoice(MOCK_INVOICE_ID, 1500.0)
        assert exc_info.value.status_code == 400
        assert "exceeds balance due" in exc_info.value.detail


@pytest.mark.asyncio
async def test_payment_on_draft_invoice_rejected():
    """Test that recording a payment on a draft invoice is rejected."""
    draft_invoice = {
        "_id": ObjectId(MOCK_INVOICE_ID),
        "client_id": MOCK_CLIENT_ID,
        "payment_status": "draft",
        "grand_total": 1000.0,
        "amount_paid": 0.0,
        "balance_due": 1000.0,
        "due_date": datetime.now(timezone.utc) + timedelta(days=30)
    }

    with patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=draft_invoice)):
        with pytest.raises(HTTPException) as exc_info:
            await InvoiceService.record_payment_on_invoice(MOCK_INVOICE_ID, 500.0)
        assert exc_info.value.status_code == 400
        assert "draft" in exc_info.value.detail


@pytest.mark.asyncio
async def test_delete_invoice_only_draft():
    """Test that only draft invoices can be deleted."""
    draft_invoice = {
        "_id": ObjectId(MOCK_INVOICE_ID),
        "client_id": MOCK_CLIENT_ID,
        "payment_status": "draft",
        "due_date": datetime.now(timezone.utc) + timedelta(days=30)
    }
    sent_invoice = {**draft_invoice, "payment_status": "sent"}

    mock_collection = MagicMock()
    mock_collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))

    # Draft can be deleted
    with patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=draft_invoice)), \
         patch("app.services.invoice_service.get_invoices_collection", return_value=mock_collection):
        result = await InvoiceService.delete_invoice(MOCK_INVOICE_ID)
        assert result is True

    # Sent cannot be deleted
    with patch("app.services.invoice_service.InvoiceService.get_invoice", AsyncMock(return_value=sent_invoice)):
        with pytest.raises(HTTPException) as exc_info:
            await InvoiceService.delete_invoice(MOCK_INVOICE_ID)
        assert exc_info.value.status_code == 400
        assert "draft" in exc_info.value.detail


def test_overdue_detection():
    """Test in-memory overdue detection based on due_date."""
    # Invoice past due date with 'sent' status -> should become overdue
    past_due_invoice = {
        "_id": ObjectId(),
        "client_id": MOCK_CLIENT_ID,
        "payment_status": "sent",
        "due_date": datetime.now(timezone.utc) - timedelta(days=5),
        "balance_due": 500.0
    }
    result = InvoiceService._check_overdue(past_due_invoice)
    assert result["payment_status"] == "overdue"

    # Invoice NOT past due date with 'sent' status -> should stay sent
    future_due_invoice = {
        "_id": ObjectId(),
        "client_id": MOCK_CLIENT_ID,
        "payment_status": "sent",
        "due_date": datetime.now(timezone.utc) + timedelta(days=10),
        "balance_due": 500.0
    }
    result = InvoiceService._check_overdue(future_due_invoice)
    assert result["payment_status"] == "sent"

    # Already paid invoice -> should stay paid regardless of due_date
    paid_invoice = {
        "_id": ObjectId(),
        "client_id": MOCK_CLIENT_ID,
        "payment_status": "paid",
        "due_date": datetime.now(timezone.utc) - timedelta(days=5),
        "balance_due": 0.0
    }
    result = InvoiceService._check_overdue(paid_invoice)
    assert result["payment_status"] == "paid"
