from fastapi import APIRouter, Depends, HTTPException, status, Response
from app.services.auth_service import get_current_user, RoleChecker, verify_client_access
from app.models.invoice_model import InvoiceCreate, InvoiceUpdate, InvoiceResponse, PaymentStatus
from app.services.invoice_service import InvoiceService
from app.services.pdf_service import PDFService
from app.services.email_service import EmailService

router = APIRouter()

allow_write = RoleChecker(["admin", "employee"])
allow_any = RoleChecker(["admin", "employee", "client"])


@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice_in: InvoiceCreate,
    current_user: dict = Depends(allow_write)
):
    """
    Create a new invoice in 'draft' status.
    Auto-generates invoice number and sets balance_due = grand_total.
    Requires 'admin' or 'employee' role.
    """
    invoice = await InvoiceService.create_invoice(invoice_in, current_user["user_id"])
    return invoice


@router.get("/{id}", response_model=InvoiceResponse)
async def get_invoice(
    id: str,
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve a specific invoice by ID.
    Automatically detects overdue status based on due_date.
    Clients can only retrieve their own invoices.
    """
    invoice = await InvoiceService.get_invoice(id)
    verify_client_access(current_user, invoice["client_id"])
    return invoice


@router.put("/{id}", response_model=InvoiceResponse)
async def update_invoice(
    id: str,
    update_in: InvoiceUpdate,
    current_user: dict = Depends(allow_write)
):
    """
    Update invoice details (subtotal, tax, due_date).
    Only allowed in 'draft' status. Recalculates grand_total and balance_due server-side.
    Requires 'admin' or 'employee' role.
    """
    updated = await InvoiceService.update_invoice(id, update_in, current_user["user_id"])
    return updated


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    id: str,
    current_user: dict = Depends(allow_write)
):
    """
    Delete an invoice. Only draft invoices can be deleted.
    Requires 'admin' or 'employee' role.
    """
    await InvoiceService.delete_invoice(id)
    return None


@router.post("/{id}/status", response_model=InvoiceResponse)
async def change_invoice_status(
    id: str,
    new_status: PaymentStatus,
    current_user: dict = Depends(allow_write)
):
    """
    Update invoice payment status with transition validation.
    Valid transitions:
      - draft -> sent
      - sent -> paid | partially_paid | overdue
      - partially_paid -> paid | overdue
      - overdue -> paid | partially_paid
    Requires 'admin' or 'employee' role.
    """
    updated = await InvoiceService.change_status(id, new_status, current_user["user_id"])
    return updated


@router.post("/{id}/generate-pdf")
async def generate_invoice_pdf(
    id: str,
    current_user: dict = Depends(allow_any)
):
    """
    Generate PDF for an invoice.
    """
    invoice = await InvoiceService.get_invoice(id)
    verify_client_access(current_user, invoice["client_id"])

    pdf_bytes = await PDFService.generate_invoice_pdf(invoice)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={invoice['invoice_number']}.pdf"
        }
    )


@router.post("/{id}/send")
async def send_invoice_email(
    id: str,
    current_user: dict = Depends(allow_write)
):
    """
    Send invoice email to client with PDF attached.
    Requires 'admin' or 'employee' role.
    """
    invoice = await InvoiceService.get_invoice(id)
    
    pdf_bytes = await PDFService.generate_invoice_pdf(invoice)
    client_email = f"client_{invoice['client_id']}@example.com"
    
    success = await EmailService.send_invoice_email(invoice, client_email, pdf_bytes)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email")

    return {
        "status": "success",
        "message": f"Email containing invoice '{invoice['invoice_number']}' dispatched to client."
    }
