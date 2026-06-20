# Invoice Management API Contract

Provides CRUD operations, payment status tracking, balance management, PDF generation, and email automation for invoices.

## Base Path
`/api/invoices`

## Authorization
All endpoints require a JSON Web Token (JWT) in the `Authorization` header as a Bearer token:
`Authorization: Bearer <token>`

---

## 1. Create Invoice
Creates a new invoice in `draft` status with auto-generated invoice number.

* **Method**: `POST`
* **Path**: `/api/invoices/`
* **Required Roles**: `admin`, `employee`
* **Request Body** (`application/json`):
  ```json
  {
    "client_id": "60d5ec499b17ac18c8d0e512",
    "quotation_id": "60d5ec499b17ac18c8d0e520",
    "subtotal": 6500.00,
    "tax_amount": 1111.50,
    "grand_total": 7611.50,
    "due_date": "2026-07-19T00:00:00Z"
  }
  ```
  > **Note**: `grand_total` is recalculated server-side as `subtotal + tax_amount`. The value sent in the request is ignored.
  > `due_date` defaults to 30 days from creation if omitted.

* **Response** (`201 Created`):
  ```json
  {
    "_id": "60d5ec499b17ac18c8d0e530",
    "invoice_number": "INV-20260619-001",
    "client_id": "60d5ec499b17ac18c8d0e512",
    "quotation_id": "60d5ec499b17ac18c8d0e520",
    "subtotal": 6500.00,
    "tax_amount": 1111.50,
    "grand_total": 7611.50,
    "amount_paid": 0.0,
    "balance_due": 7611.50,
    "due_date": "2026-07-19T00:00:00Z",
    "payment_status": "draft",
    "created_at": "2026-06-19T08:00:00Z",
    "created_by": "employee_user"
  }
  ```

---

## 2. Get Invoice
Retrieves an invoice by ID. Automatically detects overdue status if due_date has passed.

* **Method**: `GET`
* **Path**: `/api/invoices/{id}`
* **Required Roles**: `admin`, `employee`, `client` (Client is restricted to own invoices).
* **Response** (`200 OK`): Invoice response object.

---

## 3. Update Invoice
Updates invoice financial details. Only allowed in `draft` status.
Server recalculates `grand_total = subtotal + tax_amount` and `balance_due = grand_total - amount_paid`.

* **Method**: `PUT`
* **Path**: `/api/invoices/{id}`
* **Required Roles**: `admin`, `employee`
* **Request Body** (`application/json`): Optional fields `subtotal`, `tax_amount`, `due_date`.
* **Response** (`200 OK`): Updated invoice response.

---

## 4. Delete Invoice
Deletes an invoice. Only `draft` invoices can be deleted.

* **Method**: `DELETE`
* **Path**: `/api/invoices/{id}`
* **Required Roles**: `admin`, `employee`
* **Response** (`204 No Content`).

---

## 5. Change Status
Updates invoice payment status with transition validation.

* **Method**: `POST`
* **Path**: `/api/invoices/{id}/status`
* **Required Roles**: `admin`, `employee`
* **Query Parameters**:
  - `new_status` (string, required): Enum `draft`, `sent`, `paid`, `partially_paid`, `overdue`.
* **Valid Transitions**:
  | From | To |
  |------|-----|
  | `draft` | `sent` |
  | `sent` | `paid`, `partially_paid`, `overdue` |
  | `partially_paid` | `paid`, `overdue` |
  | `overdue` | `paid`, `partially_paid` |
* **Response** (`200 OK`): Updated invoice response.

---

## 6. Generate PDF
Triggers PDF compilation for the invoice.

* **Method**: `POST`
* **Path**: `/api/invoices/{id}/generate-pdf`
* **Required Roles**: `admin`, `employee`, `client` (requires client ID authorization match).
* **Response** (`200 OK`):
  ```json
  {
    "status": "success",
    "message": "PDF generated for invoice 'INV-20260619-001'",
    "download_url": "/api/invoices/60d5ec499b17ac18c8d0e530/download-pdf"
  }
  ```

---

## 7. Send Email
Sends invoice email to client.

* **Method**: `POST`
* **Path**: `/api/invoices/{id}/send`
* **Required Roles**: `admin`, `employee`
* **Response** (`200 OK`):
  ```json
  {
    "status": "success",
    "message": "Email containing invoice 'INV-20260619-001' dispatched to client."
  }
  ```

---

## Financial Integrity Rules

1. `grand_total` is always recomputed as `subtotal + tax_amount` on the server.
2. `balance_due` is always `grand_total - amount_paid`.
3. Payments exceeding `balance_due` are rejected (no overpayment without explicit flag).
4. When `balance_due` reaches 0, status auto-transitions to `paid`.
5. When a partial payment is recorded, status auto-transitions to `partially_paid`.
6. Overdue detection is automatic: if `due_date < now` and status is `sent` or `partially_paid`, the response returns `overdue`.
