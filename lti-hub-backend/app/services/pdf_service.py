import os
import logging
from jinja2 import Environment, FileSystemLoader

# Attempt to import weasyprint. If it fails (e.g. missing GTK3 on Windows), fallback to a mock generator.
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except Exception as e:
    WEASYPRINT_AVAILABLE = False
    logging.warning(f"WeasyPrint could not be loaded. Falling back to mock PDF generation. Error: {e}")

# Setup Jinja2 environment
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


class PDFService:

    @staticmethod
    def _render_html(template_name: str, context: dict) -> str:
        """Renders a Jinja2 template with the given context."""
        template = env.get_template(template_name)
        return template.render(**context)

    @staticmethod
    def _generate_pdf_bytes(html_content: str) -> bytes:
        """Converts HTML string to PDF bytes using WeasyPrint (or mock)."""
        if WEASYPRINT_AVAILABLE:
            return HTML(string=html_content).write_pdf()
        else:
            # Mock PDF generation for testing/development environments missing GTK
            return b"%PDF-1.4\n%Mock PDF Content due to missing WeasyPrint/GTK\n" + html_content.encode('utf-8')

    @staticmethod
    async def generate_proposal_pdf(proposal: dict) -> bytes:
        """Generates a PDF for a Proposal."""
        html_content = PDFService._render_html("proposal_template.html", {"proposal": proposal})
        return PDFService._generate_pdf_bytes(html_content)

    @staticmethod
    async def generate_quotation_pdf(quotation: dict) -> bytes:
        """Generates a PDF for a Quotation."""
        html_content = PDFService._render_html("quotation_template.html", {"quotation": quotation})
        return PDFService._generate_pdf_bytes(html_content)

    @staticmethod
    async def generate_invoice_pdf(invoice: dict) -> bytes:
        """Generates a PDF for an Invoice."""
        html_content = PDFService._render_html("invoice_template.html", {"invoice": invoice})
        return PDFService._generate_pdf_bytes(html_content)
