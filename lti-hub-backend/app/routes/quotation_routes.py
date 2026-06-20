from fastapi import APIRouter, Depends, HTTPException, status, Response
from typing import List
from app.services.auth_service import get_current_user, RoleChecker, verify_client_access
from app.models.quotation_model import QuotationCreate, QuotationUpdate, QuotationResponse, QuotationStatus
from app.services.quotation_service import QuotationService
from app.services.pdf_service import PDFService
from app.services.email_service import EmailService

router = APIRouter()

# Role checks
allow_write = RoleChecker(["admin", "employee"])
allow_any = RoleChecker(["admin", "employee", "client"])

@router.post("/", response_model=QuotationResponse, status_code=status.HTTP_201_CREATED)
async def create_quotation(
    quotation_in: QuotationCreate,
    current_user: dict = Depends(allow_write)
):
    """
    Create a new quotation.
    Requires 'admin' or 'employee' role.
    """
    quotation = await QuotationService.create_quotation(quotation_in, current_user["user_id"])
    return quotation

@router.get("/{id}", response_model=QuotationResponse)
async def get_quotation(
    id: str,
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve a specific quotation by ID.
    Clients can only retrieve their own quotations.
    """
    quotation = await QuotationService.get_quotation(id)
    verify_client_access(current_user, quotation["client_id"])
    return quotation

@router.put("/{id}", response_model=QuotationResponse)
async def update_quotation(
    id: str,
    update_in: QuotationUpdate,
    current_user: dict = Depends(allow_write)
):
    """
    Update quotation details.
    Requires 'admin' or 'employee' role.
    """
    updated = await QuotationService.update_quotation(id, update_in, current_user["user_id"])
    return updated

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quotation(
    id: str,
    current_user: dict = Depends(allow_write)
):
    """
    Delete a quotation.
    Requires 'admin' or 'employee' role.
    """
    await QuotationService.delete_quotation(id)
    return None

@router.post("/{id}/status", response_model=QuotationResponse)
async def change_quotation_status(
    id: str,
    new_status: QuotationStatus,
    current_user: dict = Depends(allow_any)
):
    """
    Update quotation status.
    - Admin/Employee can send or approve/reject.
    - Client can only transition to 'approved' or 'rejected'.
    """
    quotation = await QuotationService.get_quotation(id)
    verify_client_access(current_user, quotation["client_id"])

    user_role = current_user.get("role")
    if user_role == "client" and new_status == QuotationStatus.SENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clients cannot mark a quotation as 'sent'."
        )

    updated = await QuotationService.change_status(id, new_status, current_user["user_id"])
    return updated

@router.post("/{id}/generate-pdf")
async def generate_quotation_pdf(
    id: str,
    current_user: dict = Depends(allow_any)
):
    """
    Generate PDF for a quotation.
    """
    quotation = await QuotationService.get_quotation(id)
    verify_client_access(current_user, quotation["client_id"])

    pdf_bytes = await PDFService.generate_quotation_pdf(quotation)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={quotation['quotation_number']}.pdf"
        }
    )

@router.post("/{id}/send")
async def send_quotation_email(
    id: str,
    current_user: dict = Depends(allow_write)
):
    """
    Send quotation email to the client with PDF attached.
    Requires 'admin' or 'employee' role.
    """
    quotation = await QuotationService.get_quotation(id)
    
    pdf_bytes = await PDFService.generate_quotation_pdf(quotation)
    client_email = f"client_{quotation['client_id']}@example.com"
    
    success = await EmailService.send_quotation_email(quotation, client_email, pdf_bytes)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email")

    return {
        "status": "success",
        "message": f"Email containing quotation '{quotation['quotation_number']}' dispatched to client."
    }

@router.post("/{id}/convert")
async def convert_quotation(
    id: str,
    current_user: dict = Depends(allow_write)
):
    """
    Convert an approved quotation to a Draft Invoice.
    Requires 'admin' or 'employee' role.
    """
    # Returns the created invoice dict
    invoice = await QuotationService.convert_to_invoice(id, current_user["user_id"])
    # Convert _id to string for response
    invoice["_id"] = str(invoice["_id"])
    invoice["due_date"] = invoice["due_date"].isoformat()
    invoice["created_at"] = invoice["created_at"].isoformat()
    return {
        "status": "success",
        "message": f"Quotation converted successfully.",
        "invoice": invoice
    }
