from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.services.auth_service import get_current_user, RoleChecker, verify_client_access
from app.models.project_model import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectStatus
from app.services.project_service import ProjectService

router = APIRouter()

allow_write = RoleChecker(["admin", "employee"])
allow_any = RoleChecker(["admin", "employee", "client"])


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    current_user: dict = Depends(allow_write)
):
    """
    Create a new client project in 'planning' status.
    Requires 'admin' or 'employee' role.
    """
    project = await ProjectService.create_project(project_in, current_user["user_id"])
    return project


@router.get("/{id}", response_model=ProjectResponse)
async def get_project(
    id: str,
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve a specific project by ID.
    Clients can only retrieve their own projects.
    """
    project = await ProjectService.get_project(id)
    verify_client_access(current_user, project["client_id"])
    return project


@router.get("/client/{client_id}", response_model=List[ProjectResponse])
async def get_client_projects(
    client_id: str,
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve all projects for a specific client.
    Clients can only retrieve their own projects.
    """
    verify_client_access(current_user, client_id)
    projects = await ProjectService.get_projects_by_client(client_id)
    return projects


@router.put("/{id}", response_model=ProjectResponse)
async def update_project(
    id: str,
    update_in: ProjectUpdate,
    current_user: dict = Depends(allow_write)
):
    """
    Update project details.
    Requires 'admin' or 'employee' role.
    """
    updated_project = await ProjectService.update_project(id, update_in, current_user["user_id"])
    return updated_project


@router.post("/{id}/status", response_model=ProjectResponse)
async def change_project_status(
    id: str,
    new_status: ProjectStatus,
    current_user: dict = Depends(allow_write)
):
    """
    Update project status.
    Requires 'admin' or 'employee' role.
    """
    updated_project = await ProjectService.change_status(id, new_status, current_user["user_id"])
    return updated_project


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    id: str,
    current_user: dict = Depends(allow_write)
):
    """
    Delete a project. Only 'planning' projects can be deleted.
    Requires 'admin' or 'employee' role.
    """
    await ProjectService.delete_project(id)
    return None
