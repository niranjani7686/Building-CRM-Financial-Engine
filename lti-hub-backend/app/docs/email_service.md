# Email Automation Service Contract

The Email Automation Service is responsible for dispatching system emails with generated PDF attachments to clients.

## Endpoints Utilizing Email Service

The following endpoints trigger the internal `EmailService` to dispatch an email. If the SMTP credentials are not valid or not set, the service logs the attempt as a `[SIMULATED EMAIL]` and returns a success response for development purposes.

### 1. Send Proposal Email
* **Method**: `POST`
* **Path**: `/api/proposals/{id}/send`
* **Required Roles**: `admin`, `employee`
* **Action**: Generates the Proposal PDF and attaches it to an email sent to the client.
* **Response** (`200 OK`): Success message.

### 2. Send Quotation Email
* **Method**: `POST`
* **Path**: `/api/quotations/{id}/send`
* **Required Roles**: `admin`, `employee`
* **Action**: Generates the Quotation PDF and attaches it to an email sent to the client.
* **Response** (`200 OK`): Success message.

### 3. Send Invoice Email
* **Method**: `POST`
* **Path**: `/api/invoices/{id}/send`
* **Required Roles**: `admin`, `employee`
* **Action**: Generates the Invoice PDF and attaches it to an email sent to the client.
* **Response** (`200 OK`): Success message.

---

## Technical Details

1. **SMTP Configuration**: Uses standard Python `smtplib` and `email.message`.
2. **Environment Variables**:
   - `SMTP_HOST` (default: `smtp.example.com`)
   - `SMTP_PORT` (default: `587`)
   - `SMTP_USER`
   - `SMTP_PASS`
   - `FROM_EMAIL` (default: `finance@lti-hub.com`)
3. **Simulation Mode**: If `SMTP_HOST` is left as `smtp.example.com`, the system bypasses actual SMTP connection and instead simulates the email transmission by logging to standard output.
