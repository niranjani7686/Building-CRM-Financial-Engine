import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
from fastapi import HTTPException
from app.models.proposal_model import ProposalCreate, ProposalUpdate, ProposalStatus, PricingDetails
from app.services.proposal_service import ProposalService, validate_client_exists
from app.services.auth_service import verify_client_access

# Mock client_id and proposal_id
MOCK_CLIENT_ID = str(ObjectId())
MOCK_PROPOSAL_ID = str(ObjectId())

@pytest.mark.asyncio
async def test_validate_client_exists():
    """Test client validation against p5_clients collection."""
    # Test invalid ObjectId format
    with pytest.raises(HTTPException) as exc_info:
        await validate_client_exists("invalid-id")
    assert exc_info.value.status_code == 400
    assert "Invalid client_id format" in exc_info.value.detail

    # Test client exists mock
    mock_db = MagicMock()
    mock_db["p5_clients"].find_one = AsyncMock(return_value={"_id": ObjectId(MOCK_CLIENT_ID)})
    
    with patch("app.services.proposal_service.Database.db", mock_db):
        res = await validate_client_exists(MOCK_CLIENT_ID)
        assert res is True

@pytest.mark.asyncio
async def test_create_proposal():
    """Test that creating a proposal validates client, sets status to draft, and version to 1."""
    proposal_in = ProposalCreate(
        client_id=MOCK_CLIENT_ID,
        title="Test Proposal",
        scope_of_work="Scope details",
        pricing_details=PricingDetails(amount=5000.0, currency="USD", billing_type="fixed"),
        deliverables=["Deliverable 1"],
        timeline_milestones=[]
    )

    mock_inserted_id = ObjectId()
    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id=mock_inserted_id))

    # Mock get_proposal to return the created document
    mock_proposal_doc = proposal_in.model_dump()
    mock_proposal_doc.update({
        "_id": mock_inserted_id,
        "status": "draft",
        "version": 1,
        "created_by": "user123",
        "created_at": "2026-06-19T07:45:00Z"
    })
    
    with patch("app.services.proposal_service.validate_client_exists", AsyncMock(return_value=True)), \
         patch("app.services.proposal_service.get_proposals_collection", return_value=mock_collection):
        
        result = await ProposalService.create_proposal(proposal_in, "user123")
        
        assert result["status"] == "draft"
        assert result["version"] == 1
        assert result["created_by"] == "user123"
        assert result["_id"] == mock_inserted_id
        mock_collection.insert_one.assert_called_once()

@pytest.mark.asyncio
async def test_update_proposal_draft_status():
    """Test updating a proposal in 'draft' status does NOT bump the version."""
    proposal_doc = {
        "_id": ObjectId(MOCK_PROPOSAL_ID),
        "client_id": MOCK_CLIENT_ID,
        "title": "Old Draft Title",
        "scope_of_work": "Old scope",
        "pricing_details": {"amount": 5000.0, "currency": "USD", "billing_type": "fixed"},
        "deliverables": [],
        "timeline_milestones": [],
        "status": "draft",
        "version": 1,
        "created_by": "user123",
        "created_at": "2026-06-19T07:45:00Z",
        "updated_at": "2026-06-19T07:45:00Z",
        "activity_log": []
    }

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()

    update_in = ProposalUpdate(title="New Draft Title")

    with patch("app.services.proposal_service.ProposalService.get_proposal", AsyncMock(return_value=proposal_doc)), \
         patch("app.services.proposal_service.get_proposals_collection", return_value=mock_collection):
        
        await ProposalService.update_proposal(MOCK_PROPOSAL_ID, update_in, "user123")
        
        # Check that update_one was called, setting status/fields without a version bump
        call_args = mock_collection.update_one.call_args[0][1]
        assert "$set" in call_args
        assert call_args["$set"]["title"] == "New Draft Title"
        assert "version" not in call_args["$set"] # No version bump

@pytest.mark.asyncio
async def test_update_proposal_sent_status():
    """Test updating a proposal in 'sent' status bumps version and saves snapshot in version_history."""
    proposal_doc = {
        "_id": ObjectId(MOCK_PROPOSAL_ID),
        "client_id": MOCK_CLIENT_ID,
        "title": "Sent Title",
        "scope_of_work": "Sent scope",
        "pricing_details": {"amount": 5000.0, "currency": "USD", "billing_type": "fixed", "details": ""},
        "deliverables": [],
        "timeline_milestones": [],
        "status": "sent",
        "version": 1,
        "created_by": "user123",
        "created_at": "2026-06-19T07:45:00Z",
        "updated_at": "2026-06-19T07:45:00Z",
        "activity_log": []
    }

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()

    update_in = ProposalUpdate(title="Revised Title")

    with patch("app.services.proposal_service.ProposalService.get_proposal", AsyncMock(return_value=proposal_doc)), \
         patch("app.services.proposal_service.get_proposals_collection", return_value=mock_collection):
        
        await ProposalService.update_proposal(MOCK_PROPOSAL_ID, update_in, "user123")
        
        call_args = mock_collection.update_one.call_args[0][1]
        
        # Check version is bumped to 2 and status reset to draft
        assert call_args["$set"]["version"] == 2
        assert call_args["$set"]["status"] == "draft"
        # Check snapshot is pushed into version_history
        assert "$push" in call_args
        assert "version_history" in call_args["$push"]
        snapshot = call_args["$push"]["version_history"]
        assert snapshot["version"] == 1
        assert snapshot["title"] == "Sent Title"

@pytest.mark.asyncio
async def test_proposal_status_transitions():
    """Test that valid and invalid status transitions are correctly handled by the state machine."""
    draft_doc = {
        "_id": ObjectId(MOCK_PROPOSAL_ID),
        "client_id": MOCK_CLIENT_ID,
        "status": "draft",
        "version": 1,
        "created_by": "user123",
        "created_at": "2026-06-19T07:45:00Z",
        "updated_at": "2026-06-19T07:45:00Z"
    }

    sent_doc = {**draft_doc, "status": "sent"}

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()

    # 1. Test Valid transition: draft -> sent
    with patch("app.services.proposal_service.ProposalService.get_proposal", AsyncMock(return_value=draft_doc)), \
         patch("app.services.proposal_service.get_proposals_collection", return_value=mock_collection):
        
        await ProposalService.change_status(MOCK_PROPOSAL_ID, ProposalStatus.SENT, "user123")
        mock_collection.update_one.assert_called_once()
        
    # 2. Test Invalid transition: draft -> accepted (must go to sent first)
    with patch("app.services.proposal_service.ProposalService.get_proposal", AsyncMock(return_value=draft_doc)):
        with pytest.raises(HTTPException) as exc_info:
            await ProposalService.change_status(MOCK_PROPOSAL_ID, ProposalStatus.ACCEPTED, "user123")
        assert exc_info.value.status_code == 400
        assert "Invalid status transition" in exc_info.value.detail

    # 3. Test Valid transition: sent -> accepted
    mock_collection.reset_mock()
    with patch("app.services.proposal_service.ProposalService.get_proposal", AsyncMock(return_value=sent_doc)), \
         patch("app.services.proposal_service.get_proposals_collection", return_value=mock_collection):
        
        await ProposalService.change_status(MOCK_PROPOSAL_ID, ProposalStatus.ACCEPTED, "user123")
        mock_collection.update_one.assert_called_once()

def test_client_access_control():
    """Test auth service helper verify_client_access handles scopes & ownership correctly."""
    admin_user = {"user_id": "u1", "role": "admin", "client_id": None}
    employee_user = {"user_id": "u2", "role": "employee", "client_id": None}
    client_user = {"user_id": "u3", "role": "client", "client_id": "c123"}

    # Admins can access anything
    assert verify_client_access(admin_user, "c123") is True
    assert verify_client_access(admin_user, "c456") is True

    # Employees can access anything
    assert verify_client_access(employee_user, "c123") is True

    # Client user can access their own client id
    assert verify_client_access(client_user, "c123") is True

    # Client user CANNOT access a different client id
    with pytest.raises(HTTPException) as exc_info:
        verify_client_access(client_user, "c456")
    assert exc_info.value.status_code == 403
    assert "Access denied" in exc_info.value.detail
