from pydantic import BaseModel, Field
from typing import List, Optional

class FinancialSummary(BaseModel):
    total_invoiced: float = Field(0.0, description="Sum of grand_total for all non-draft invoices")
    total_paid: float = Field(0.0, description="Sum of amount_paid across all invoices")
    total_outstanding: float = Field(0.0, description="Sum of balance_due across all invoices")
    total_overdue: float = Field(0.0, description="Sum of balance_due for overdue invoices")

class ProposalMetrics(BaseModel):
    total_proposals: int = Field(0, description="Total number of proposals")
    draft_count: int = Field(0, description="Number of proposals in draft")
    sent_count: int = Field(0, description="Number of proposals sent")
    accepted_count: int = Field(0, description="Number of proposals accepted")
    rejected_count: int = Field(0, description="Number of proposals rejected")

class RevenueByMonth(BaseModel):
    month: str = Field(..., description="Month in YYYY-MM format")
    revenue: float = Field(0.0, description="Total verified payment amounts in this month")

class AnalyticsDashboardResponse(BaseModel):
    financial_summary: FinancialSummary
    proposal_metrics: ProposalMetrics
    recent_revenue: List[RevenueByMonth] = Field(default_factory=list)
