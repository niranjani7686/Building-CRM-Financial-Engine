# PDF Generation Service Contract

The PDF Generation Service is a shared utility that converts document models (Proposal, Quotation, Invoice) into downloadable PDF files using Jinja2 HTML templates and WeasyPrint (or a mock fallback if GTK dependencies are unavailable in the host OS).

## Endpoints Integrating PDF Service

The following endpoints return a binary PDF stream with `application/pdf` Content-Type:

### 1. Generate Proposal PDF
* **Method**: `POST`
* **Path**: `/api/proposals/{id}/generate-pdf`
* **Required Roles**: `admin`, `employee`, `client` (Client restricted to own)
* **Response** (`200 OK`): Binary PDF data.
* **Headers**: `Content-Disposition: attachment; filename=proposal_{id}.pdf`

### 2. Generate Quotation PDF
* **Method**: `POST`
* **Path**: `/api/quotations/{id}/generate-pdf`
* **Required Roles**: `admin`, `employee`, `client` (Client restricted to own)
* **Response** (`200 OK`): Binary PDF data.
* **Headers**: `Content-Disposition: attachment; filename={quotation_number}.pdf`

### 3. Generate Invoice PDF
* **Method**: `POST`
* **Path**: `/api/invoices/{id}/generate-pdf`
* **Required Roles**: `admin`, `employee`, `client` (Client restricted to own)
* **Response** (`200 OK`): Binary PDF data.
* **Headers**: `Content-Disposition: attachment; filename={invoice_number}.pdf`

---

## Technical Details

1. **Templating Engine**: `Jinja2` is used to inject JSON data from MongoDB into standard HTML templates (`app/templates/*.html`).
2. **PDF Engine**: `WeasyPrint` is used for high-fidelity HTML-to-PDF rendering.
3. **Environment Resilience**: The `pdf_service.py` safely wraps the `WeasyPrint` import. If the underlying OS lacks GTK3 binaries (common on Windows without MSYS2/GTK setup), the service gracefully falls back to generating a "Mock PDF Content" byte stream. This ensures APIs never crash due to missing native libraries.
