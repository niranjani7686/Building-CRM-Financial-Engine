import os
import smtplib
import logging
from email.message import EmailMessage
from typing import Optional

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables for SMTP configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "user@example.com")
SMTP_PASS = os.getenv("SMTP_PASS", "password")
FROM_EMAIL = os.getenv("FROM_EMAIL", "finance@lti-hub.com")

class EmailService:
    
    @staticmethod
    async def send_email(
        to_email: str, 
        subject: str, 
        body: str, 
        attachment_bytes: Optional[bytes] = None,
        attachment_name: Optional[str] = None
    ) -> bool:
        """
        Sends an email using configured SMTP settings.
        If SMTP credentials are not valid (or left as defaults), it logs the email payload and simulates success.
        """
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        msg.set_content(body)

        if attachment_bytes and attachment_name:
            msg.add_attachment(
                attachment_bytes, 
                maintype='application', 
                subtype='pdf', 
                filename=attachment_name
            )

        # In a real environment with valid credentials, we connect to SMTP.
        # Here we simulate or try.
        if SMTP_HOST == "smtp.example.com":
            logger.info(f"[SIMULATED EMAIL] To: {to_email} | Subject: {subject} | Attachment: {attachment_name}")
            return True

        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            logger.info(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}. Error: {e}")
            return False

    @staticmethod
    async def send_proposal_email(proposal: dict, client_email: str, pdf_bytes: bytes) -> bool:
        subject = f"Proposal: {proposal['title']}"
        body = f"Hello,\n\nPlease find attached the proposal '{proposal['title']}'.\n\nThank you."
        return await EmailService.send_email(
            to_email=client_email,
            subject=subject,
            body=body,
            attachment_bytes=pdf_bytes,
            attachment_name=f"proposal_{proposal['_id']}.pdf"
        )

    @staticmethod
    async def send_quotation_email(quotation: dict, client_email: str, pdf_bytes: bytes) -> bool:
        subject = f"Quotation: {quotation['quotation_number']}"
        body = f"Hello,\n\nPlease find attached quotation {quotation['quotation_number']} valid until {quotation['valid_until']}.\n\nThank you."
        return await EmailService.send_email(
            to_email=client_email,
            subject=subject,
            body=body,
            attachment_bytes=pdf_bytes,
            attachment_name=f"{quotation['quotation_number']}.pdf"
        )

    @staticmethod
    async def send_invoice_email(invoice: dict, client_email: str, pdf_bytes: bytes) -> bool:
        subject = f"Invoice: {invoice['invoice_number']}"
        body = f"Hello,\n\nPlease find attached invoice {invoice['invoice_number']} for the amount of ${invoice['balance_due']:.2f}.\n\nThank you."
        return await EmailService.send_email(
            to_email=client_email,
            subject=subject,
            body=body,
            attachment_bytes=pdf_bytes,
            attachment_name=f"{invoice['invoice_number']}.pdf"
        )
