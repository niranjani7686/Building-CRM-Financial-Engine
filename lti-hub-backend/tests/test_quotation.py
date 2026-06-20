import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
from fastapi import HTTPException
from app.models.quotation_model import QuotationCreate, QuotationUpdate, QuotationStatus, LineItem
from app.services.quotation_service import QuotationService

MOCK_CLIENT_ID = str(ObjectId())
MOCK_QUOTATION_ID = str(ObjectId())

def test_calculate_quotation_totals():
    """Test the server-side arithmetic for quotation line items and final pricing totals."""
    line_items = [
        LineItem(description="Item A", quantity=2, unit_price=100.0),
        LineItem(description="Item B", quantity=1.5, unit_price=200.0)
    ]
    
    # 2 * 100 = 200
    # 1.5 * 200 = 300
    # Subtotal = 500
    # Discount 10% = 50. Taxable = 450
    # Tax 18% = 81. Grand Total = 531
    totals = QuotationService.calculate_quotation_totals(
        line_items=line_items,
        discount_percentage=10.0,
        tax_rate=0.18
    )
    
    assert totals["subtotal"] == 500.0
    assert totals["discount_amount"] == 50.0
    assert totals["tax_amount"] == 81.0
    assert totals["grand_total"] == 531.0
    assert totals["line_items"][0]["total"] == 200.0
    assert totals["line_items"][1]["total"] == 300.0

@pytest.mark.asyncio
async def test_create_quotation():
    """Test quotation creation sets correct initial status and generated fields."""
    quotation_in = QuotationCreate(
        client_id=MOCK_CLIENT_ID,
        line_items=[LineItem(description="Item A", quantity=10, unit_price=5.5)],
        discount_percentage=0.0,
        tax_rate=0.10
    )
    
    mock_inserted_id = ObjectId()
    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id=mock_inserted_id))
    
    with patch("app.services.quotation_service.validate_client_exists", AsyncMock(return_value=True)), \
         patch("app.services.quotation_service.get_quotations_collection", return_value=mock_collection), \
         patch("app.services.quotation_service.generate_quotation_number", AsyncMock(return_value="QT-20260619-001")):
        
        result = await QuotationService.create_quotation(quotation_in, "employee_1")
        
        assert result["quotation_number"] == "QT-20260619-001"
        assert result["status"] == QuotationStatus.DRAFT.value
        assert result["subtotal"] == 55.0
        assert result["tax_amount"] == 5.5
        assert result["grand_total"] == 60.5
        assert result["created_by"] == "employee_1"
        assert result["_id"] == mock_inserted_id

@pytest.mark.asyncio
async def test_update_quotation_draft():
    """Test updating quotation re-computes totals and allows editing in draft status."""
    quotation_doc = {
        "_id": ObjectId(MOCK_QUOTATION_ID),
        "client_id": MOCK_CLIENT_ID,
        "quotation_number": "QT-20260619-001",
        "line_items": [{"description": "Item A", "quantity": 1.0, "unit_price": 100.0, "total": 100.0}],
        "subtotal": 100.0,
        "discount_amount": 0.0,
        "tax_amount": 0.0,
        "grand_total": 100.0,
        "status": "draft",
        "created_at": "2026-06-19T07:54:00Z"
    }

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()

    update_in = QuotationUpdate(
        line_items=[LineItem(description="Item A", quantity=2.0, unit_price=100.0)], # Quantity changed to 2
        discount_percentage=10.0 # Add discount
    )

    with patch("app.services.quotation_service.QuotationService.get_quotation", AsyncMock(return_value=quotation_doc)), \
         patch("app.services.quotation_service.get_quotations_collection", return_value=mock_collection):
        
        await QuotationService.update_quotation(MOCK_QUOTATION_ID, update_in, "employee_1")
        
        # Verify update content has the recalculated totals (subtotal=200, discount=20, grand_total=180)
        call_args = mock_collection.update_one.call_args[0][1]
        assert call_args["$set"]["subtotal"] == 200.0
        assert call_args["$set"]["discount_amount"] == 20.0
        assert call_args["$set"]["grand_total"] == 180.0

@pytest.mark.asyncio
async def test_quotation_status_transitions():
    """Test quotation state machine restrictions."""
    draft_doc = {
        "_id": ObjectId(MOCK_QUOTATION_ID),
        "client_id": MOCK_CLIENT_ID,
        "status": "draft"
    }
    sent_doc = {**draft_doc, "status": "sent"}
    approved_doc = {**draft_doc, "status": "approved"}

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()

    # Valid: draft -> sent
    with patch("app.services.quotation_service.QuotationService.get_quotation", AsyncMock(return_value=draft_doc)), \
         patch("app.services.quotation_service.get_quotations_collection", return_value=mock_collection):
        await QuotationService.change_status(MOCK_QUOTATION_ID, QuotationStatus.SENT, "user")
        mock_collection.update_one.assert_called_once()

    # Invalid: draft -> approved
    with patch("app.services.quotation_service.QuotationService.get_quotation", AsyncMock(return_value=draft_doc)):
        with pytest.raises(HTTPException) as exc_info:
            await QuotationService.change_status(MOCK_QUOTATION_ID, QuotationStatus.APPROVED, "user")
        assert exc_info.value.status_code == 400

    # Valid: sent -> approved
    mock_collection.reset_mock()
    with patch("app.services.quotation_service.QuotationService.get_quotation", AsyncMock(return_value=sent_doc)), \
         patch("app.services.quotation_service.get_quotations_collection", return_value=mock_collection):
        await QuotationService.change_status(MOCK_QUOTATION_ID, QuotationStatus.APPROVED, "user")
        mock_collection.update_one.assert_called_once()

@pytest.mark.asyncio
async def test_convert_to_invoice():
    """Test that converting approved quotations creates the draft invoice correctly and blocks non-approved."""
    approved_quotation = {
        "_id": ObjectId(MOCK_QUOTATION_ID),
        "client_id": MOCK_CLIENT_ID,
        "quotation_number": "QT-20260619-001",
        "subtotal": 1000.0,
        "tax_amount": 180.0,
        "grand_total": 1180.0,
        "status": "approved"
    }

    draft_quotation = {**approved_quotation, "status": "draft"}

    # Mock DB collections
    mock_invoices_col = MagicMock()
    mock_invoices_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_quotations_col = MagicMock()
    mock_quotations_col.update_one = AsyncMock()

    # Test conversion fails for non-approved quotation
    with patch("app.services.quotation_service.QuotationService.get_quotation", AsyncMock(return_value=draft_quotation)):
        with pytest.raises(HTTPException) as exc_info:
            await QuotationService.convert_to_invoice(MOCK_QUOTATION_ID, "user_1")
        assert exc_info.value.status_code == 400
        assert "must be 'approved'" in exc_info.value.detail

    # Test conversion succeeds for approved quotation
    with patch("app.services.quotation_service.QuotationService.get_quotation", AsyncMock(return_value=approved_quotation)), \
         patch("app.services.quotation_service.get_invoices_collection", return_value=mock_invoices_col), \
         patch("app.services.quotation_service.get_quotations_collection", return_value=mock_quotations_col), \
         patch("app.services.quotation_service.generate_invoice_number", AsyncMock(return_value="INV-20260619-001")):
        
        invoice = await QuotationService.convert_to_invoice(MOCK_QUOTATION_ID, "user_1")
        
        assert invoice["invoice_number"] == "INV-20260619-001"
        assert invoice["client_id"] == MOCK_CLIENT_ID
        assert invoice["quotation_id"] == MOCK_QUOTATION_ID
        assert invoice["subtotal"] == 1000.0
        assert invoice["tax_amount"] == 180.0
        assert invoice["grand_total"] == 1180.0
        assert invoice["balance_due"] == 1180.0
        assert invoice["amount_paid"] == 0.0
        assert invoice["payment_status"] == "draft"
        mock_invoices_col.insert_one.assert_called_once()
        mock_quotations_col.update_one.assert_called_once()
