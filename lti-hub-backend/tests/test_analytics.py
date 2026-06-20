import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.analytics_service import AnalyticsService

@pytest.mark.asyncio
async def test_get_financial_summary():
    """Test aggregation of financial totals."""
    mock_collection = MagicMock()
    mock_cursor_list = AsyncMock()
    
    # First call is for main aggregation, second for overdue
    mock_collection.aggregate.return_value.to_list = AsyncMock(side_effect=[
        [{"total_invoiced": 1000.0, "total_paid": 400.0, "total_outstanding": 600.0}],
        [{"total_overdue": 200.0}]
    ])

    with patch("app.services.analytics_service.get_invoices_collection", return_value=mock_collection):
        result = await AnalyticsService.get_financial_summary()

        assert result.total_invoiced == 1000.0
        assert result.total_paid == 400.0
        assert result.total_outstanding == 600.0
        assert result.total_overdue == 200.0


@pytest.mark.asyncio
async def test_get_financial_summary_empty():
    """Test aggregation handles empty database."""
    mock_collection = MagicMock()
    mock_collection.aggregate.return_value.to_list = AsyncMock(return_value=[])

    with patch("app.services.analytics_service.get_invoices_collection", return_value=mock_collection):
        result = await AnalyticsService.get_financial_summary()

        assert result.total_invoiced == 0.0
        assert result.total_paid == 0.0
        assert result.total_outstanding == 0.0
        assert result.total_overdue == 0.0


@pytest.mark.asyncio
async def test_get_proposal_metrics():
    """Test aggregation of proposal counts by status."""
    mock_collection = MagicMock()
    mock_collection.aggregate.return_value.to_list = AsyncMock(return_value=[
        {"_id": "draft", "count": 2},
        {"_id": "sent", "count": 3},
        {"_id": "accepted", "count": 1}
    ])

    with patch("app.services.analytics_service.get_proposals_collection", return_value=mock_collection):
        result = await AnalyticsService.get_proposal_metrics()

        assert result.total_proposals == 6
        assert result.draft_count == 2
        assert result.sent_count == 3
        assert result.accepted_count == 1
        assert result.rejected_count == 0


@pytest.mark.asyncio
async def test_get_revenue_over_time():
    """Test aggregation of verified payments grouped by month."""
    mock_collection = MagicMock()
    mock_collection.aggregate.return_value.to_list = AsyncMock(return_value=[
        {"_id": "2026-06", "revenue": 500.0},
        {"_id": "2026-05", "revenue": 1200.0}
    ])

    with patch("app.services.analytics_service.get_payments_collection", return_value=mock_collection):
        result = await AnalyticsService.get_revenue_over_time()

        assert len(result) == 2
        assert result[0].month == "2026-06"
        assert result[0].revenue == 500.0
        assert result[1].month == "2026-05"
        assert result[1].revenue == 1200.0
