# Payment Tracking API Contract

Provides endpoints to record payments against invoices, verify payments, and retrieve payment histories and outstanding balances.

## Base Path
`/api/payments`

## Authorization
All endpoints require a JSON Web Token (JWT) in the `Authorization` header as a Bearer token:
`Authorization: Bearer <token>`

---

## 1. Record Payment
Records a payment against a specific invoice. Automatically updates the invoice's `amount_paid`, `balance_due`, and `payment_status`.

* **Method**: `POST`
* **Path**: `/api/payments/`
* **Required Roles**: `admin`, `employee`
* **Request Body** (`application/json`):
  ```json
  {
    "invoice_id": "60d5ec499b17ac18c8d0e530",
    "client_id": "60d5ec499b17ac18c8d0e512",
    "payment_amount": 1000.00,
    "payment_method": "bank_transfer",
    "reference_number": "TXN-987654321",
    "payment_date": "2026-06-19T10:00:00Z"
  }
  ```
  > **Note**: `payment_date` defaults to the current UTC time if omitted.

* **Response** (`201 Created`):
  ```json
  {
    "_id": "60d5ec499b17ac18c8d0e600",
    "invoice_id": "60d5ec499b17ac18c8d0e530",
    "client_id": "60d5ec499b17ac18c8d0e512",
    "payment_amount": 1000.00,
    "payment_date": "2026-06-19T10:00:00Z",
    "payment_method": "bank_transfer",
    "reference_number": "TXN-987654321",
    "status": "pending",
    "created_at": "2026-06-19T10:00:00Z"
  }
  ```

---

## 2. Get Payment
Retrieves a specific payment by its ID.

* **Method**: `GET`
* **Path**: `/api/payments/{id}`
* **Required Roles**: `admin`, `employee`, `client` (Client restricted to own payments).
* **Response** (`200 OK`): Payment response object.

---

## 3. Verify Payment
Marks a pending payment as verified.

* **Method**: `POST`
* **Path**: `/api/payments/{id}/verify`
* **Required Roles**: `admin`, `employee`
* **Response** (`200 OK`):
  ```json
  {
    "_id": "60d5ec499b17ac18c8d0e600",
    "status": "verified",
    "...": "..."
  }
  ```

---

## 4. Get Payment History by Invoice
Retrieves all payments for a specific invoice, ordered by date descending.

* **Method**: `GET`
* **Path**: `/api/payments/invoice/{invoice_id}/history`
* **Required Roles**: `admin`, `employee`, `client` (Client implicitly restricted by invoice lookup).
* **Response** (`200 OK`): Array of payment response objects.

---

## 5. Get Payment History by Client
Retrieves all payments for a specific client, ordered by date descending.

* **Method**: `GET`
* **Path**: `/api/payments/client/{client_id}/history`
* **Required Roles**: `admin`, `employee`, `client` (Client restricted to own ID).
* **Response** (`200 OK`): Array of payment response objects.

---

## 6. Get Outstanding Balances
Retrieves all invoices that have a balance due > 0.

* **Method**: `GET`
* **Path**: `/api/payments/outstanding/balances`
* **Required Roles**: `admin`, `employee`, `client` (Client restricted to own balances).
* **Query Parameters**:
  - `client_id` (optional string): Filter by client ID.
* **Response** (`200 OK`):
  ```json
  {
    "outstanding_invoices": [
      {
        "_id": "60d5ec499b17ac18c8d0e530",
        "invoice_number": "INV-20260619-001",
        "client_id": "60d5ec499b17ac18c8d0e512",
        "grand_total": 7611.50,
        "amount_paid": 1000.00,
        "balance_due": 6611.50,
        "due_date": "2026-07-19T00:00:00Z",
        "payment_status": "partially_paid"
      }
    ],
    "count": 1
  }
  ```

---

## 7. Get Overdue Invoices
Retrieves all invoices that are past their due date and have an outstanding balance.

* **Method**: `GET`
* **Path**: `/api/payments/overdue/invoices`
* **Required Roles**: `admin`, `employee`, `client` (Client restricted to own invoices).
* **Query Parameters**:
  - `client_id` (optional string): Filter by client ID.
* **Response** (`200 OK`):
  ```json
  {
    "overdue_invoices": [],
    "count": 0
  }
  ```

---

## Financial Integrity Rules
1. Payments cannot be recorded against a `draft` invoice.
2. Payments cannot be recorded if the invoice is already `paid`.
3. The `payment_amount` cannot exceed the invoice's `balance_due`. Overpayment is strictly rejected.
4. When a payment is recorded, the corresponding invoice's `amount_paid` and `balance_due` are immediately recalculated.
