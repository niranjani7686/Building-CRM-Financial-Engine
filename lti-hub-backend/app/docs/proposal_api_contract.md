# Proposal Management API Contract

Provides CRUD operations, status management, PDF generation triggers, and email automation hooks for proposals in the CRM system.

## Base Path
`/api/proposals`

## Authorization
All endpoints require a JSON Web Token (JWT) in the `Authorization` header as a Bearer token:
`Authorization: Bearer <token>`

---

## 1. Create Proposal
Creates a new proposal in `draft` status.

* **Method**: `POST`
* **Path**: `/api/proposals/`
* **Required Roles**: `admin`, `employee`
* **Request Body** (`application/json`):
  ```json
  {
    "client_id": "60d5ec499b17ac18c8d0e512",
    "title": "Website Redesign & CRM Integration",
    "scope_of_work": "Design and build a modern corporate website integrated with custom HubSpot pipelines.",
    "pricing_details": {
      "amount": 12500.00,
      "currency": "USD",
      "billing_type": "milestone",
      "details": "50% upfront, 50% upon delivery"
    },
    "deliverables": [
      "Figma UX/UI mockup design files",
      "Responsive React-based frontend web app",
      "FastAPI integration layer",
      "Database schema and setup documentation"
    ],
    "timeline_milestones": [
      {
        "title": "UI Mockups Approval",
        "description": "Approve final interactive web mockups",
        "due_date": "2026-07-15"
      },
      {
        "title": "Beta Deployment",
        "description": "Deploy working web application to staging",
        "due_date": "2026-08-30"
      }
    ]
  }
  ```
* **Response** (`201 Created`):
  ```json
  {
    "_id": "60d5ec499b17ac18c8d0e515",
    "client_id": "60d5ec499b17ac18c8d0e512",
    "title": "Website Redesign & CRM Integration",
    "scope_of_work": "Design and build a modern corporate website integrated with custom HubSpot pipelines.",
    "pricing_details": {
      "amount": 12500.00,
      "currency": "USD",
      "billing_type": "milestone",
      "details": "50% upfront, 50% upon delivery"
    },
    "deliverables": [
      "Figma UX/UI mockup design files",
      "Responsive React-based frontend web app",
      "FastAPI integration layer",
      "Database schema and setup documentation"
    ],
    "timeline_milestones": [
      {
        "title": "UI Mockups Approval",
        "description": "Approve final interactive web mockups",
        "due_date": "2026-07-15"
      },
      {
        "title": "Beta Deployment",
        "description": "Deploy working web application to staging",
        "due_date": "2026-08-30"
      }
    ],
    "status": "draft",
    "version": 1,
    "created_by": "employee_user",
    "created_at": "2026-06-19T07:45:00Z",
    "updated_at": "2026-06-19T07:45:00Z",
    "activity_log": [
      {
        "action": "created",
        "performed_by": "employee_user",
        "timestamp": "2026-06-19T07:45:00Z",
        "details": "Initial proposal draft created."
      }
    ],
    "version_history": []
  }
  ```

---

## 2. Get Proposal
Retrieves a proposal by its 24-character hexadecimal MongoDB ObjectId.

* **Method**: `GET`
* **Path**: `/api/proposals/{id}`
* **Required Roles**: `admin`, `employee`, `client` (Client role is restricted to viewing proposals where `proposal.client_id == user.client_id`).
* **Response** (`200 OK`): Matches the shape of the created proposal response.

---

## 3. Update Proposal
Updates details of an existing proposal.
- **Draft Version**: Edits apply immediately to the current version.
- **Sent Version**: Bumps `version` count by 1, clones current state to `version_history`, updates fields, and resets status to `draft`.
- **Accepted/Rejected**: Updates are blocked.

* **Method**: `PUT`
* **Path**: `/api/proposals/{id}`
* **Required Roles**: `admin`, `employee`
* **Request Body** (`application/json`): Contains any subset of editable fields (e.g., `title`, `scope_of_work`, `pricing_details`, `deliverables`, `timeline_milestones`).
* **Response** (`200 OK`): The updated proposal response.

---

## 4. Delete Proposal
Deletes a proposal document from the database.

* **Method**: `DELETE`
* **Path**: `/api/proposals/{id}`
* **Required Roles**: `admin`, `employee`
* **Response** (`204 No Content`): Empty response indicating successful deletion.

---

## 5. Change Status
Transitions status of a proposal according to state machine rules:
- `draft` -> `sent`
- `sent` -> `accepted`
- `sent` -> `rejected`

* **Method**: `POST`
* **Path**: `/api/proposals/{id}/status`
* **Required Roles**: 
  - `admin`, `employee` can transition to any status.
  - `client` can only transition from `sent` to `accepted` or `rejected` (requires client ID authorization match).
* **Query Parameters**:
  - `new_status` (string, required): Enum `draft`, `sent`, `accepted`, `rejected`.
* **Response** (`200 OK`): Updated proposal response.

---

## 6. Generate PDF
Triggers PDF compilation for the proposal.

* **Method**: `POST`
* **Path**: `/api/proposals/{id}/generate-pdf`
* **Required Roles**: `admin`, `employee`, `client` (requires client ID authorization match).
* **Response** (`200 OK`):
  ```json
  {
    "status": "success",
    "message": "PDF generated for proposal 'Website Redesign & CRM Integration' (ID: 60d5ec499b17ac18c8d0e515)",
    "download_url": "/api/proposals/60d5ec499b17ac18c8d0e515/download-pdf"
  }
  ```

---

## 7. Send Email
Sends a proposal notification email to the client contacts.

* **Method**: `POST`
* **Path**: `/api/proposals/{id}/send`
* **Required Roles**: `admin`, `employee`
* **Response** (`200 OK`):
  ```json
  {
    "status": "success",
    "message": "Email containing proposal 'Website Redesign & CRM Integration' dispatched to client."
  }
  ```
