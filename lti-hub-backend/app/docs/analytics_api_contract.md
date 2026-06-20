# Analytics APIs Contract

Provides data aggregation endpoints for business dashboards. Combines proposal metrics, invoice financials, and payment history into high-level summaries.

## Base Path
`/api/analytics`

## Authorization
All endpoints require a JSON Web Token (JWT) in the `Authorization` header as a Bearer token.
Client roles can only retrieve data belonging to their own `client_id`.

---

## 1. Get Dashboard Metrics
Retrieves comprehensive dashboard metrics including financials, proposals, and revenue over time.

* **Method**: `GET`
* **Path**: `/api/analytics/dashboard`
* **Required Roles**: `admin`, `employee`, `client`
* **Query Parameters**:
  - `client_id` (optional string): Filter metrics by client ID. Automatically enforced for client role.
* **Response** (`200 OK`):
  ```json
  {
    "financial_summary": {
      "total_invoiced": 25000.00,
      "total_paid": 15000.00,
      "total_outstanding": 10000.00,
      "total_overdue": 2500.00
    },
    "proposal_metrics": {
      "total_proposals": 12,
      "draft_count": 2,
      "sent_count": 5,
      "accepted_count": 4,
      "rejected_count": 1
    },
    "recent_revenue": [
      {
        "month": "2026-06",
        "revenue": 5000.00
      },
      {
        "month": "2026-05",
        "revenue": 10000.00
      }
    ]
  }
  ```

---

## 2. Get Financial Summary
Retrieves only the financial metrics based on invoice data.

* **Method**: `GET`
* **Path**: `/api/analytics/financials`
* **Required Roles**: `admin`, `employee`, `client`
* **Query Parameters**:
  - `client_id` (optional string): Filter metrics by client ID.
* **Response** (`200 OK`): `financial_summary` object from the dashboard response.

---

## 3. Get Proposal Metrics
Retrieves only the proposal pipeline counts.

* **Method**: `GET`
* **Path**: `/api/analytics/proposals`
* **Required Roles**: `admin`, `employee`, `client`
* **Query Parameters**:
  - `client_id` (optional string): Filter metrics by client ID.
* **Response** (`200 OK`): `proposal_metrics` object from the dashboard response.
