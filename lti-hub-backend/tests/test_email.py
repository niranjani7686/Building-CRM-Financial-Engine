import pytest
from unittest.mock import patch, MagicMock
from app.services.email_service import EmailService

@pytest.mark.asyncio
async def test_send_email_simulation(caplog):
    """Test that default config simulates email sending and logs it."""
    import logging
    caplog.set_level(logging.INFO)
    
    # Ensure SMTP_HOST is the default simulation trigger
    with patch("app.services.email_service.SMTP_HOST", "smtp.example.com"):
        result = await EmailService.send_email(
            to_email="test@client.com",
            subject="Test Subject",
            body="Test Body",
            attachment_bytes=b"dummy_pdf_bytes",
            attachment_name="test.pdf"
        )
        
        assert result is True
        assert "[SIMULATED EMAIL]" in caplog.text
        assert "To: test@client.com" in caplog.text


@pytest.mark.asyncio
async def test_send_proposal_email():
    """Test send_proposal_email formatting and delegation."""
    proposal = {
        "_id": "prop123",
        "title": "SEO Services"
    }
    
    with patch("app.services.email_service.EmailService.send_email") as mock_send:
        mock_send.return_value = True
        
        result = await EmailService.send_proposal_email(proposal, "client@domain.com", b"pdf")
        
        assert result is True
        mock_send.assert_called_once_with(
            to_email="client@domain.com",
            subject="Proposal: SEO Services",
            body="Hello,\n\nPlease find attached the proposal 'SEO Services'.\n\nThank you.",
            attachment_bytes=b"pdf",
            attachment_name="proposal_prop123.pdf"
        )


@pytest.mark.asyncio
async def test_send_quotation_email():
    """Test send_quotation_email formatting and delegation."""
    quotation = {
        "quotation_number": "QUO-999",
        "valid_until": "2026-12-31"
    }
    
    with patch("app.services.email_service.EmailService.send_email") as mock_send:
        mock_send.return_value = True
        
        result = await EmailService.send_quotation_email(quotation, "client@domain.com", b"pdf")
        
        assert result is True
        mock_send.assert_called_once()
        args = mock_send.call_args[1]
        assert args["subject"] == "Quotation: QUO-999"
        assert args["attachment_name"] == "QUO-999.pdf"


@pytest.mark.asyncio
async def test_send_invoice_email():
    """Test send_invoice_email formatting and delegation."""
    invoice = {
        "invoice_number": "INV-555",
        "balance_due": 1500.50
    }
    
    with patch("app.services.email_service.EmailService.send_email") as mock_send:
        mock_send.return_value = True
        
        result = await EmailService.send_invoice_email(invoice, "client@domain.com", b"pdf")
        
        assert result is True
        mock_send.assert_called_once()
        args = mock_send.call_args[1]
        assert args["subject"] == "Invoice: INV-555"
        assert "1500.50" in args["body"]
        assert args["attachment_name"] == "INV-555.pdf"


@pytest.mark.asyncio
async def test_send_email_real_smtp_failure():
    """Test SMTP failure handling."""
    with patch("app.services.email_service.SMTP_HOST", "real.smtp.com"):
        with patch("smtplib.SMTP") as mock_smtp:
            # Simulate SMTP connection failure
            mock_smtp.side_effect = Exception("Connection refused")
            
            result = await EmailService.send_email(
                to_email="test@client.com",
                subject="Test Subject",
                body="Test Body"
            )
            
            assert result is False
