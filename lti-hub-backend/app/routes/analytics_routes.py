from fastapi import APIRouter, Depends, Query
from app.services.auth_service import get_current_user, RoleChecker, verify_client_access
from app.models.analytics_model import AnalyticsDashboardResponse, FinancialSummary, ProposalMetrics
from app.services.analytics_service import AnalyticsService

router = APIRouter()

allow_write = RoleChecker(["admin", "employee"])
allow_any = RoleChecker(["admin", "employee", "client"])


@router.get("/dashboard", response_model=AnalyticsDashboardResponse)
async def get_dashboard_metrics(
    client_id: str = Query(None, description="Optional client ID to filter metrics"),
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve comprehensive dashboard metrics including financials, proposals, and revenue.
    Clients can only retrieve their own metrics.
    """
    # Enforce client access boundaries
    if current_user.get("role") == "client":
        client_id = current_user.get("client_id")
    elif client_id and current_user.get("role") in ["admin", "employee"]:
        pass # allowed to filter

    metrics = await AnalyticsService.get_dashboard_metrics(client_id)
    return metrics


@router.get("/financials", response_model=FinancialSummary)
async def get_financial_summary(
    client_id: str = Query(None, description="Optional client ID to filter metrics"),
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve isolated financial metrics.
    """
    if current_user.get("role") == "client":
        client_id = current_user.get("client_id")

    summary = await AnalyticsService.get_financial_summary(client_id)
    return summary


@router.get("/proposals", response_model=ProposalMetrics)
async def get_proposal_metrics(
    client_id: str = Query(None, description="Optional client ID to filter metrics"),
    current_user: dict = Depends(allow_any)
):
    """
    Retrieve isolated proposal metrics.
    """
    if current_user.get("role") == "client":
        client_id = current_user.get("client_id")

    metrics = await AnalyticsService.get_proposal_metrics(client_id)
    return metrics
