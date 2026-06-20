# Quotation Management API Contract

Provides CRUD operations, calculations, status tracking, PDF generation, email automation triggers, and invoice conversion for quotations.

## Base Path
`/api/quotations`

## Authorization
All endpoints require a JSON Web Token (JWT) in the `Authorization` header as a Bearer token:
`Authorization: Bearer <token>`

---

## 1. Create Quotation
Creates a new quotation. All totals (subtotal, discount, tax, grand total) are calculated on the server-side.

* **Method**: `POST`
* **Path**: `/api/quotations/`
* **Required Roles**: `admin`, `employee`
* **Request Body** (`application/json`):
  ```json
  {
    "client_id": "60d5ec499b17ac18c8d0e512",
    "line_items": [
      {
        "description": "Custom CRM Integration Setup",
        "quantity": 1,
        "unit_price": 5000.00
      },
      {
        "description": "Database Migration (hours)",
        "quantity": 10,
        "unit_price": 150.00
      }
    ],
    "discount_percentage": 5.0,
    "tax_rate": 0.18
  }
  ```
* **Response** (`201 Created`):
  ```json
  {
    "_id": "60d5ec499b17ac18c8d0e520",
    "client_id": "60d5ec499b17ac18c8d0e512",
    "quotation_number": "QT-20260619-001",
    "line_items": [
      {
        "description": "Custom CRM Integration Setup",
        "quantity": 1,
        "unit_price": 5000.00,
        "total": 5000.00
      },
      {
        "description": "Database Migration (hours)",
        "quantity": 10,
        "unit_price": 150.00,
        "total": 1500.00
      }
    ],
    "subtotal": 6500.00,
    "discount_amount": 325.00,
    "tax_amount": 1111.50,
    "grand_total": 7286.50,
    "status": "draft",
    "created_at": "2026-06-19T07:54:00Z"
  }
  ```

---

## 2. Get Quotation
Retrieves details of a quotation.

* **Method**: `GET`
* **Path**: `/api/quotations/{id}`
* **Required Roles**: `admin`, `employee`, `client` (Client role is restricted to viewing quotations where `quotation.client_id == user.client_id`).
* **Response** (`200 OK`): Matches the shape of the created quotation response.

---

## 3. Update Quotation
Updates lines, discount, or tax for a quotation. Recalculates all pricing server-side.
Updates are only allowed in `draft` or `sent` status.

* **Method**: `PUT`
* **Path**: `/api/quotations/{id}`
* **Required Roles**: `admin`, `employee`
* **Request Body** (`application/json`): Contains optional `line_items`, `discount_percentage`, and `tax_rate`.
* **Response** (`200 OK`): Updated quotation response.

---

## 4. Delete Quotation
Deletes a quotation.

* **Method**: `DELETE`
* **Path**: `/api/quotations/{id}`
* **Required Roles**: `admin`, `employee`
* **Response** (`204 No Content`): Empty response indicating successful deletion.

---

## 5. Change Status
Updates status of a quotation.
- `draft` -> `sent`
- `sent` -> `approved`
- `sent` -> `rejected`

* **Method**: `POST`
* **Path**: `/api/quotations/{id}/status`
* **Required Roles**:
  - `admin`, `employee` can transition to any status.
  - `client` can transition from `sent` to `approved` or `rejected` (requires client ID authorization match).
* **Query Parameters**:
  - `new_status` (string, required): Enum `draft`, `sent`, `approved`, `rejected`.
* **Response** (`200 OK`): Updated quotation response.

---

## 6. Generate PDF
Triggers PDF compilation for the quotation.

* **Method**: `POST`
* **Path**: `/api/quotations/{id}/generate-pdf`
* **Required Roles**: `admin`, `employee`, `client` (requires client ID authorization match).
* **Response** (`200 OK`):
  ```json
  {
    "status": "success",
    "message": "PDF generated for quotation 'QT-20260619-001'",
    "download_url": "/api/quotations/60d5ec499b17ac18c8d0e520/download-pdf"
  }
  ```

---

## 7. Send Email
Triggers email dispatch to the client contacts.

* **Method**: `POST`
* **Path**: `/api/quotations/{id}/send`
* **Required Roles**: `admin`, `employee`
* **Response** (`200 OK`):
  ```json
  {
    "status": "success",
    "message": "Email containing quotation 'QT-20260619-001' dispatched."
  }
  ```

---

## 8. Convert to Invoice
Converts an `approved` quotation into a new `Draft` invoice.

* **Method**: `POST`
* **Path**: `/api/quotations/{id}/convert`
* **Required Roles**: `admin`, `employee`
* **Response** (`200 OK`):
  ```json
  {
    "status": "success",
    "message": "Quotation converted successfully.",
    "invoice": {
      "_id": "60d5ec499b17ac18c8d0e530",
      "invoice_number": "INV-20260619-001",
      "client_id": "60d5ec499b17ac18c8d0e512",
      "quotation_id": "60d5ec499b17ac18c8d0e520",
      "subtotal": 6500.00,
      "tax_amount": 1111.50,
      "grand_total": 7286.50,
      "amount_paid": 0.0,
      "balance_due": 7286.50,
      "due_date": "2026-07-19T07:54:00.000Z",
      "payment_status": "draft",
      "created_at": "2026-06-19T07:54:00.000Z",
      "created_by": "employee_user"
    }
  }
  ```
