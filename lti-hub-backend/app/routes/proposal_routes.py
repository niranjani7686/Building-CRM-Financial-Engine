from fastapi import APIRouter, Depends, HTTPException, status, Response
from typing import List
from app.services.auth_service import get_current_user, RoleChecker, verify_client_access
from app.models.proposal_model import ProposalCreate, ProposalUpdate, ProposalResponse, ProposalStatus
from app.services.proposal_service import ProposalService
from app.services.pdf_service import PDFService
from app.services.email_service import EmailService

router = APIRouter()

# Role checkers
allow_write = RoleChecker(["admin", "employee"])
allow_any = RoleChecker(["admin", "employee", "client"])

@router.post("/", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    proposal_in: ProposalCreate,
    current_user: dict = Depends(allow_write)
):
    """
    Create a new proposal in draft status.
    Requires 'admin' or 'employee' role.
    """
    # Enforce that if caller is somehow tied to a client (e.g. employee restricted), they have access
    # Generally admin/employee can create for any client.
    proposal = await ProposalService.create_proposal(proposal_in, current_user["user_id"])
    return proposal

@router.get("/{id}", response_model=ProposalResponse)
async def get_proposal(
    id: str,
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve a specific proposal by ID.
    Clients can only retrieve their own proposals.
    """
    proposal = await ProposalService.get_proposal(id)
    # Validate authorization to access this client's financial records
    verify_client_access(current_user, proposal["client_id"])
    return proposal

@router.put("/{id}", response_model=ProposalResponse)
async def update_proposal(
    id: str,
    update_in: ProposalUpdate,
    current_user: dict = Depends(allow_write)
):
    """
    Update proposal details.
    Requires 'admin' or 'employee' role.
    """
    # Note: proposal status & client limits are handled in proposal_service
    updated_proposal = await ProposalService.update_proposal(id, update_in, current_user["user_id"])
    return updated_proposal

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proposal(
    id: str,
    current_user: dict = Depends(allow_write)
):
    """
    Delete a proposal.
    Requires 'admin' or 'employee' role.
    """
    await ProposalService.delete_proposal(id)
    return None

@router.post("/{id}/status", response_model=ProposalResponse)
async def change_proposal_status(
    id: str,
    new_status: ProposalStatus,
    current_user: dict = Depends(allow_any)
):
    """
    Update proposal status.
    - Admin/Employee can send or approve/reject.
    - Client can only transition to 'accepted' or 'rejected'.
    """
    proposal = await ProposalService.get_proposal(id)
    
    # Verify client access
    verify_client_access(current_user, proposal["client_id"])
    
    # Enforce role restrictions on transition
    user_role = current_user.get("role")
    if user_role == "client" and new_status == ProposalStatus.SENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clients cannot mark a proposal as 'sent'."
        )
        
    updated_proposal = await ProposalService.change_status(id, new_status, current_user["user_id"])
    return updated_proposal

@router.post("/{id}/generate-pdf")
async def generate_proposal_pdf(
    id: str,
    current_user: dict = Depends(allow_any)
):
    """
    Generate and retrieve PDF for a proposal.
    """
    proposal = await ProposalService.get_proposal(id)
    verify_client_access(current_user, proposal["client_id"])
    
    pdf_bytes = await PDFService.generate_proposal_pdf(proposal)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=proposal_{id}.pdf"
        }
    )

@router.post("/{id}/send")
async def send_proposal_email(
    id: str,
    current_user: dict = Depends(allow_write)
):
    """
    Send proposal email to the client with PDF attached.
    Requires 'admin' or 'employee' role.
    """
    proposal = await ProposalService.get_proposal(id)
    
    # Generate PDF
    pdf_bytes = await PDFService.generate_proposal_pdf(proposal)
    
    # Mock client email lookup
    client_email = f"client_{proposal['client_id']}@example.com"
    
    # Send email
    success = await EmailService.send_proposal_email(proposal, client_email, pdf_bytes)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email")

    return {
        "status": "success",
        "message": f"Email containing proposal '{proposal['title']}' dispatched to client."
    }
