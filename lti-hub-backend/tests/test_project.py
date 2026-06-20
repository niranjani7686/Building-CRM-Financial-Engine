import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
from fastapi import HTTPException
from app.models.project_model import ProjectCreate, ProjectUpdate, ProjectStatus
from app.services.project_service import ProjectService

MOCK_CLIENT_ID = str(ObjectId())
MOCK_PROJECT_ID = str(ObjectId())

@pytest.mark.asyncio
async def test_create_project():
    """Test project creation sets default status and timestamp."""
    project_in = ProjectCreate(
        client_id=MOCK_CLIENT_ID,
        name="Test Project",
        budget=5000.0
    )

    mock_inserted_id = ObjectId()
    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id=mock_inserted_id))

    with patch("app.services.project_service.validate_client_exists", AsyncMock(return_value=True)), \
         patch("app.services.project_service.get_client_projects_collection", return_value=mock_collection):

        result = await ProjectService.create_project(project_in, "employee_1")

        assert result["name"] == "Test Project"
        assert result["status"] == "planning"
        assert result["_id"] == mock_inserted_id
        mock_collection.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_change_status():
    """Test successful status transition."""
    project = {
        "_id": ObjectId(MOCK_PROJECT_ID),
        "status": "planning"
    }

    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()

    with patch("app.services.project_service.ProjectService.get_project", AsyncMock(return_value=project)), \
         patch("app.services.project_service.get_client_projects_collection", return_value=mock_collection):

        await ProjectService.change_status(MOCK_PROJECT_ID, ProjectStatus.ACTIVE, "user_1")

        call_args = mock_collection.update_one.call_args[0][1]
        assert call_args["$set"]["status"] == "active"


@pytest.mark.asyncio
async def test_change_status_blocked():
    """Test status transition blocked if already completed."""
    project = {
        "_id": ObjectId(MOCK_PROJECT_ID),
        "status": "completed"
    }

    with patch("app.services.project_service.ProjectService.get_project", AsyncMock(return_value=project)):
        with pytest.raises(HTTPException) as exc_info:
            await ProjectService.change_status(MOCK_PROJECT_ID, ProjectStatus.ACTIVE, "user_1")
        
        assert exc_info.value.status_code == 400
        assert "Cannot change status" in exc_info.value.detail


@pytest.mark.asyncio
async def test_delete_project_planning():
    """Test deletion succeeds if planning."""
    project = {
        "_id": ObjectId(MOCK_PROJECT_ID),
        "status": "planning"
    }

    mock_collection = MagicMock()
    mock_collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))

    with patch("app.services.project_service.ProjectService.get_project", AsyncMock(return_value=project)), \
         patch("app.services.project_service.get_client_projects_collection", return_value=mock_collection):

        result = await ProjectService.delete_project(MOCK_PROJECT_ID)
        assert result is True


@pytest.mark.asyncio
async def test_delete_project_blocked():
    """Test deletion fails if not planning."""
    project = {
        "_id": ObjectId(MOCK_PROJECT_ID),
        "status": "active"
    }

    with patch("app.services.project_service.ProjectService.get_project", AsyncMock(return_value=project)):
        with pytest.raises(HTTPException) as exc_info:
            await ProjectService.delete_project(MOCK_PROJECT_ID)
        
        assert exc_info.value.status_code == 400
        assert "Only 'planning' projects can be deleted" in exc_info.value.detail
