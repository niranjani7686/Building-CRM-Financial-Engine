from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException, status
from typing import List, Optional
from app.database import get_proposals_collection, Database
from app.models.proposal_model import (
    ProposalCreate,
    ProposalUpdate,
    ProposalStatus,
    ActivityLogEntry,
    ProposalVersionSnapshot,
    PricingDetails,
    Milestone
)

async def validate_client_exists(client_id: str) -> bool:
    """
    Validates that a client exists in the database.
    TODO-INTEGRATION: Connect to the actual clients microservice/collection.
    For this module, we verify against a 'p5_clients' collection. If it doesn't exist or is empty,
    we validate standard hex ObjectIds to avoid blocking frontend integration.
    """
    if not ObjectId.is_valid(client_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid client_id format: '{client_id}'. Must be a 24-character hex string."
        )
    
    # Query database collection
    db = Database.db
    if db is not None:
        client = await db["p5_clients"].find_one({"_id": ObjectId(client_id)})
        if client:
            return True
            
        # Fallback check: if there are no clients in the database, allow it for bootstrap/testing
        count = await db["p5_clients"].count_documents({})
        if count == 0:
            return True

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Client with ID '{client_id}' does not exist."
    )

class ProposalService:
    @staticmethod
    async def create_proposal(proposal_in: ProposalCreate, user_id: str) -> dict:
        """Create a new proposal in draft status."""
        # 1. Validate client exists
        await validate_client_exists(proposal_in.client_id)

        # 2. Build proposal document
        now = datetime.now(timezone.utc)
        proposal_dict = proposal_in.model_dump()
        
        # Convert client_id string to ObjectId for database storage (or keep as string if requested, let's keep string to match Pydantic schema client_id: str, but validate ObjectId validity)
        proposal_dict.update({
            "status": ProposalStatus.DRAFT.value,
            "version": 1,
            "created_by": user_id,
            "created_at": now,
            "updated_at": now,
            "activity_log": [
                {
                    "action": "created",
                    "performed_by": user_id,
                    "timestamp": now,
                    "details": "Initial proposal draft created."
                }
            ],
            "version_history": []
        })

        collection = get_proposals_collection()
        result = await collection.insert_one(proposal_dict)
        proposal_dict["_id"] = result.inserted_id
        return proposal_dict

    @staticmethod
    async def get_proposal(proposal_id: str) -> dict:
        """Retrieve a proposal by its ID."""
        if not ObjectId.is_valid(proposal_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid proposal ID: '{proposal_id}'"
            )
        
        collection = get_proposals_collection()
        proposal = await collection.find_one({"_id": ObjectId(proposal_id)})
        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proposal with ID '{proposal_id}' not found."
            )
        return proposal

    @staticmethod
    async def update_proposal(proposal_id: str, update_in: ProposalUpdate, user_id: str) -> dict:
        """
        Update proposal details. 
        - If proposal is in 'draft' status, apply edits directly to the current version.
        - If proposal is in 'sent' status, create a version snapshot of the current state,
          increment the version counter, update details, and reset status to 'draft'.
        - If proposal is already 'accepted' or 'rejected', editing is blocked.
        """
        proposal = await ProposalService.get_proposal(proposal_id)
        current_status = proposal.get("status")

        if current_status in [ProposalStatus.ACCEPTED.value, ProposalStatus.REJECTED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot edit proposal in '{current_status}' status. It must be in 'draft' or 'sent' status."
            )

        now = datetime.now(timezone.utc)
        update_data = update_in.model_dump(exclude_unset=True)

        if not update_data:
            return proposal

        collection = get_proposals_collection()
        activity_entries = []
        
        if current_status == ProposalStatus.SENT.value:
            # Create a version snapshot of the current state before editing
            snapshot = ProposalVersionSnapshot(
                version=proposal["version"],
                title=proposal["title"],
                scope_of_work=proposal["scope_of_work"],
                pricing_details=PricingDetails(**proposal["pricing_details"]),
                deliverables=proposal["deliverables"],
                timeline_milestones=[Milestone(**m) for m in proposal["timeline_milestones"]],
                updated_at=proposal["updated_at"],
                updated_by=proposal.get("updated_by", proposal["created_by"])
            )
            
            # Increment version, add snapshot to history, and reset status to draft
            new_version = proposal["version"] + 1
            
            activity_entries.append({
                "action": "version_bumped",
                "performed_by": user_id,
                "timestamp": now,
                "details": f"Proposal updated after being sent. Version bumped from {proposal['version']} to {new_version} and reset to draft status."
            })
            
            update_query = {
                "$set": {
                    **update_data,
                    "version": new_version,
                    "status": ProposalStatus.DRAFT.value,
                    "updated_at": now,
                    "updated_by": user_id
                },
                "$push": {
                    "version_history": snapshot.model_dump(),
                    "activity_log": {
                        "$each": activity_entries
                    }
                }
            }
        else:
            # Proposal is in 'draft' status: direct edit, no version bump
            activity_entries.append({
                "action": "updated",
                "performed_by": user_id,
                "timestamp": now,
                "details": "Proposal content updated."
            })
            
            update_query = {
                "$set": {
                    **update_data,
                    "updated_at": now,
                    "updated_by": user_id
                },
                "$push": {
                    "activity_log": {
                        "$each": activity_entries
                    }
                }
            }

        await collection.update_one({"_id": ObjectId(proposal_id)}, update_query)
        return await ProposalService.get_proposal(proposal_id)

    @staticmethod
    async def change_status(proposal_id: str, new_status: ProposalStatus, user_id: str) -> dict:
        """
        Transitions the proposal status according to the state machine rules:
        - draft -> sent (locks current version)
        - sent -> accepted
        - sent -> rejected
        """
        proposal = await ProposalService.get_proposal(proposal_id)
        current_status = proposal.get("status")

        # Define valid transitions
        valid = False
        if current_status == ProposalStatus.DRAFT.value and new_status == ProposalStatus.SENT:
            valid = True
        elif current_status == ProposalStatus.SENT.value and new_status in [ProposalStatus.ACCEPTED, ProposalStatus.REJECTED]:
            valid = True

        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from '{current_status}' to '{new_status}'."
            )

        now = datetime.now(timezone.utc)
        log_entry = ActivityLogEntry(
            action="status_changed",
            performed_by=user_id,
            timestamp=now,
            details=f"Status changed from '{current_status}' to '{new_status}'."
        )

        collection = get_proposals_collection()
        await collection.update_one(
            {"_id": ObjectId(proposal_id)},
            {
                "$set": {
                    "status": new_status.value,
                    "updated_at": now,
                    "updated_by": user_id
                },
                "$push": {
                    "activity_log": log_entry.model_dump()
                }
            }
        )
        return await ProposalService.get_proposal(proposal_id)

    @staticmethod
    async def delete_proposal(proposal_id: str) -> bool:
        """Delete a proposal document from the collection."""
        # Validate existence
        await ProposalService.get_proposal(proposal_id)
        
        collection = get_proposals_collection()
        result = await collection.delete_one({"_id": ObjectId(proposal_id)})
        return result.deleted_count > 0
