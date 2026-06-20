# Client Project Management API Contract

Provides CRUD endpoints to manage top-level client projects. Projects track metadata, budgets, timelines, and execution status.

## Base Path
`/api/projects`

## Authorization
All endpoints require a JSON Web Token (JWT) in the `Authorization` header as a Bearer token:
`Authorization: Bearer <token>`

---

## 1. Create Project
Creates a new project in `planning` status.

* **Method**: `POST`
* **Path**: `/api/projects/`
* **Required Roles**: `admin`, `employee`
* **Request Body** (`application/json`):
  ```json
  {
    "client_id": "60d5ec499b17ac18c8d0e512",
    "name": "Q3 Marketing Campaign",
    "description": "Comprehensive SEO and Ads execution.",
    "start_date": "2026-07-01T00:00:00Z",
    "end_date": "2026-09-30T00:00:00Z",
    "budget": 15000.00
  }
  ```

* **Response** (`201 Created`):
  ```json
  {
    "_id": "60d5ec499b17ac18c8d0e800",
    "client_id": "60d5ec499b17ac18c8d0e512",
    "name": "Q3 Marketing Campaign",
    "description": "Comprehensive SEO and Ads execution.",
    "status": "planning",
    "start_date": "2026-07-01T00:00:00Z",
    "end_date": "2026-09-30T00:00:00Z",
    "budget": 15000.00,
    "created_at": "2026-06-19T10:00:00Z",
    "updated_at": null,
    "created_by": "employee_user"
  }
  ```

---

## 2. Get Project
Retrieves a specific project by ID.

* **Method**: `GET`
* **Path**: `/api/projects/{id}`
* **Required Roles**: `admin`, `employee`, `client` (Client restricted to own projects).
* **Response** (`200 OK`): Project response object.

---

## 3. Get Client Projects
Retrieves all projects for a specific client.

* **Method**: `GET`
* **Path**: `/api/projects/client/{client_id}`
* **Required Roles**: `admin`, `employee`, `client` (Client restricted to own ID).
* **Response** (`200 OK`): Array of project response objects.

---

## 4. Update Project
Updates project metadata (name, description, dates, budget).

* **Method**: `PUT`
* **Path**: `/api/projects/{id}`
* **Required Roles**: `admin`, `employee`
* **Request Body**: Partial update object (any field from Create except `client_id`).
* **Response** (`200 OK`): Updated project response object.

---

## 5. Change Status
Updates project status.

* **Method**: `POST`
* **Path**: `/api/projects/{id}/status`
* **Required Roles**: `admin`, `employee`
* **Query Parameters**:
  - `new_status` (string, required): Enum `planning`, `active`, `on_hold`, `completed`, `cancelled`.
* **Response** (`200 OK`): Updated project response object.
* **Constraints**: Cannot change status if already `cancelled` or `completed`.

---

## 6. Delete Project
Deletes a project.

* **Method**: `DELETE`
* **Path**: `/api/projects/{id}`
* **Required Roles**: `admin`, `employee`
* **Constraints**: Only `planning` projects can be deleted.
* **Response** (`204 No Content`).
