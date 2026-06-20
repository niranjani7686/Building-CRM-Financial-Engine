from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from app.database import get_invoices_collection, get_proposals_collection, get_payments_collection
from app.models.analytics_model import AnalyticsDashboardResponse, FinancialSummary, ProposalMetrics, RevenueByMonth

class AnalyticsService:

    @staticmethod
    async def get_financial_summary(client_id: Optional[str] = None) -> FinancialSummary:
        """
        Aggregates financial totals from the invoices collection.
        If client_id is provided, filters for that specific client.
        """
        collection = get_invoices_collection()
        match_stage = {"payment_status": {"$ne": "draft"}}
        if client_id:
            match_stage["client_id"] = client_id

        pipeline = [
            {"$match": match_stage},
            {"$group": {
                "_id": None,
                "total_invoiced": {"$sum": "$grand_total"},
                "total_paid": {"$sum": "$amount_paid"},
                "total_outstanding": {"$sum": "$balance_due"}
            }}
        ]

        result = await collection.aggregate(pipeline).to_list(1)
        
        # Calculate overdue separately based on date
        now = datetime.now(timezone.utc)
        overdue_match = {
            "payment_status": {"$nin": ["draft", "paid"]},
            "due_date": {"$lt": now},
            "balance_due": {"$gt": 0}
        }
        if client_id:
            overdue_match["client_id"] = client_id
            
        overdue_pipeline = [
            {"$match": overdue_match},
            {"$group": {
                "_id": None,
                "total_overdue": {"$sum": "$balance_due"}
            }}
        ]
        overdue_result = await collection.aggregate(overdue_pipeline).to_list(1)

        summary_data = result[0] if result else {"total_invoiced": 0.0, "total_paid": 0.0, "total_outstanding": 0.0}
        overdue_data = overdue_result[0] if overdue_result else {"total_overdue": 0.0}

        return FinancialSummary(
            total_invoiced=round(summary_data.get("total_invoiced", 0.0), 2),
            total_paid=round(summary_data.get("total_paid", 0.0), 2),
            total_outstanding=round(summary_data.get("total_outstanding", 0.0), 2),
            total_overdue=round(overdue_data.get("total_overdue", 0.0), 2)
        )

    @staticmethod
    async def get_proposal_metrics(client_id: Optional[str] = None) -> ProposalMetrics:
        """
        Aggregates proposal counts by status.
        """
        collection = get_proposals_collection()
        match_stage = {}
        if client_id:
            match_stage["client_id"] = client_id

        pipeline = [
            {"$match": match_stage},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]

        results = await collection.aggregate(pipeline).to_list(None)
        
        metrics = {"total": 0, "draft": 0, "sent": 0, "accepted": 0, "rejected": 0}
        for doc in results:
            status = doc["_id"]
            count = doc["count"]
            metrics["total"] += count
            if status in metrics:
                metrics[status] = count

        return ProposalMetrics(
            total_proposals=metrics["total"],
            draft_count=metrics["draft"],
            sent_count=metrics["sent"],
            accepted_count=metrics["accepted"],
            rejected_count=metrics["rejected"]
        )

    @staticmethod
    async def get_revenue_over_time(client_id: Optional[str] = None, months: int = 6) -> List[RevenueByMonth]:
        """
        Aggregates verified payments grouped by month (YYYY-MM format).
        Returns the last 'months' months.
        """
        collection = get_payments_collection()
        match_stage: Dict[str, Any] = {"status": "verified"}
        if client_id:
            match_stage["client_id"] = client_id

        pipeline = [
            {"$match": match_stage},
            {"$group": {
                "_id": {
                    "$dateToString": {"format": "%Y-%m", "date": "$payment_date"}
                },
                "revenue": {"$sum": "$payment_amount"}
            }},
            {"$sort": {"_id": -1}},
            {"$limit": months}
        ]

        results = await collection.aggregate(pipeline).to_list(None)
        
        revenue_list = []
        for doc in results:
            revenue_list.append(RevenueByMonth(
                month=doc["_id"],
                revenue=round(doc["revenue"], 2)
            ))
            
        return revenue_list

    @staticmethod
    async def get_dashboard_metrics(client_id: Optional[str] = None) -> AnalyticsDashboardResponse:
        """
        Combines financial summary, proposal metrics, and recent revenue into a single dashboard response.
        """
        financial = await AnalyticsService.get_financial_summary(client_id)
        proposals = await AnalyticsService.get_proposal_metrics(client_id)
        revenue = await AnalyticsService.get_revenue_over_time(client_id)
        
        return AnalyticsDashboardResponse(
            financial_summary=financial,
            proposal_metrics=proposals,
            recent_revenue=revenue
        )
