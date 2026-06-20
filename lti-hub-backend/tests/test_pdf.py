import pytest
from unittest.mock import patch, MagicMock
from app.services.pdf_service import PDFService

@pytest.mark.asyncio
async def test_generate_proposal_pdf_mock_fallback():
    """Test generating a Proposal PDF using the mock fallback."""
    proposal = {
        "title": "Website Redesign",
        "client_id": "client123",
        "status": "draft",
        "version": 1,
        "description": "Redesign corporate site.",
        "scope_of_work": "Frontend and Backend."
    }

    # Force the WEASYPRINT_AVAILABLE flag to False to test fallback logic
    with patch("app.services.pdf_service.WEASYPRINT_AVAILABLE", False):
        pdf_bytes = await PDFService.generate_proposal_pdf(proposal)
        
        # Check that it returns bytes and contains the fallback signature
        assert isinstance(pdf_bytes, bytes)
        assert b"%PDF-1.4" in pdf_bytes
        # Ensure Jinja2 injected the data correctly into the HTML that got appended
        assert b"Website Redesign" in pdf_bytes
        assert b"client123" in pdf_bytes


@pytest.mark.asyncio
async def test_generate_quotation_pdf_mock_fallback():
    """Test generating a Quotation PDF using the mock fallback."""
    quotation = {
        "quotation_number": "QUO-2026-001",
        "client_id": "client123",
        "status": "draft",
        "valid_until": "2026-12-31",
        "line_items": [
            {"description": "Design", "quantity": 1, "unit_price": 500.0, "total_price": 500.0}
        ],
        "subtotal": 500.0,
        "discount_percentage": 10.0,
        "discount_amount": 50.0,
        "tax_percentage": 10.0,
        "tax_amount": 45.0,
        "grand_total": 495.0
    }

    with patch("app.services.pdf_service.WEASYPRINT_AVAILABLE", False):
        pdf_bytes = await PDFService.generate_quotation_pdf(quotation)
        
        assert isinstance(pdf_bytes, bytes)
        assert b"%PDF-1.4" in pdf_bytes
        # Ensure Jinja2 injected the data correctly
        assert b"QUO-2026-001" in pdf_bytes
        assert b"495.0" in pdf_bytes


@pytest.mark.asyncio
async def test_generate_invoice_pdf_mock_fallback():
    """Test generating an Invoice PDF using the mock fallback."""
    invoice = {
        "invoice_number": "INV-2026-001",
        "client_id": "client123",
        "payment_status": "draft",
        "due_date": "2026-12-31",
        "subtotal": 500.0,
        "tax_amount": 45.0,
        "grand_total": 545.0,
        "amount_paid": 0.0,
        "balance_due": 545.0
    }

    with patch("app.services.pdf_service.WEASYPRINT_AVAILABLE", False):
        pdf_bytes = await PDFService.generate_invoice_pdf(invoice)
        
        assert isinstance(pdf_bytes, bytes)
        assert b"%PDF-1.4" in pdf_bytes
        # Ensure Jinja2 injected the data correctly
        assert b"INV-2026-001" in pdf_bytes
        assert b"545.0" in pdf_bytes
