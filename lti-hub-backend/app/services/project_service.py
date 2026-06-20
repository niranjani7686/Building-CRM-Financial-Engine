from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException, status
from typing import List, Optional
from app.database import get_client_projects_collection
from app.models.project_model import ProjectCreate, ProjectUpdate, ProjectStatus
from app.services.proposal_service import validate_client_exists


class ProjectService:

    @staticmethod
    async def create_project(project_in: ProjectCreate, user_id: str) -> dict:
        """
        Creates a new client project in 'planning' status.
        Validates client_id exists.
        """
        await validate_client_exists(project_in.client_id)

        now = datetime.now(timezone.utc)
        project_dict = project_in.model_dump()
        project_dict.update({
            "status": ProjectStatus.PLANNING.value,
            "created_at": now,
            "created_by": user_id,
            "updated_at": None
        })

        collection = get_client_projects_collection()
        result = await collection.insert_one(project_dict)
        project_dict["_id"] = result.inserted_id

        return project_dict

    @staticmethod
    async def get_project(project_id: str) -> dict:
        """Retrieve a specific project by ID."""
        if not ObjectId.is_valid(project_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid project ID: '{project_id}'"
            )

        collection = get_client_projects_collection()
        project = await collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found."
            )
        return project

    @staticmethod
    async def get_projects_by_client(client_id: str) -> List[dict]:
        """Retrieve all projects for a specific client."""
        if not ObjectId.is_valid(client_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid client ID: '{client_id}'"
            )

        collection = get_client_projects_collection()
        cursor = collection.find({"client_id": client_id}).sort("created_at", -1)
        projects = await cursor.to_list(length=500)
        return projects

    @staticmethod
    async def update_project(project_id: str, update_in: ProjectUpdate, user_id: str) -> dict:
        """Update project details."""
        # Ensure project exists
        await ProjectService.get_project(project_id)

        update_data = update_in.model_dump(exclude_unset=True)
        if not update_data:
            return await ProjectService.get_project(project_id)

        update_data["updated_at"] = datetime.now(timezone.utc)
        # Not tracking 'updated_by' explicitly in schema, but could be added.

        collection = get_client_projects_collection()
        await collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": update_data}
        )

        return await ProjectService.get_project(project_id)

    @staticmethod
    async def change_status(project_id: str, new_status: ProjectStatus, user_id: str) -> dict:
        """Change the status of a project."""
        project = await ProjectService.get_project(project_id)
        current = project.get("status")

        # Define valid transitions if needed. For now, we allow any logical progression.
        # But we block transitions out of CANCELLED or COMPLETED without admin intervention.
        if current in [ProjectStatus.CANCELLED.value, ProjectStatus.COMPLETED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot change status of a project that is already '{current}'."
            )

        collection = get_client_projects_collection()
        await collection.update_one(
            {"_id": ObjectId(project_id)},
            {
                "$set": {
                    "status": new_status.value,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        return await ProjectService.get_project(project_id)

    @staticmethod
    async def delete_project(project_id: str) -> bool:
        """Delete a project (only allowed if planning)."""
        project = await ProjectService.get_project(project_id)
        if project.get("status") != ProjectStatus.PLANNING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only 'planning' projects can be deleted."
            )
        
        collection = get_client_projects_collection()
        result = await collection.delete_one({"_id": ObjectId(project_id)})
        return result.deleted_count > 0
