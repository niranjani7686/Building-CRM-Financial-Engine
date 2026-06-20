import random
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import HTTPException, status
from typing import Optional
from app.database import get_invoices_collection, Database
from app.models.invoice_model import InvoiceCreate, InvoiceUpdate, PaymentStatus
from app.services.proposal_service import validate_client_exists


async def generate_invoice_number() -> str:
    """Generates a unique invoice number with the format: INV-YYYYMMDD-XXX"""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    prefix = f"INV-{date_str}"

    collection = get_invoices_collection()
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    end_of_day = start_of_day + timedelta(days=1)

    count = await collection.count_documents({
        "created_at": {
            "$gte": start_of_day,
            "$lt": end_of_day
        }
    })

    seq_number = str(count + 1).zfill(3)
    invoice_number = f"{prefix}-{seq_number}"
    exists = await collection.find_one({"invoice_number": invoice_number})
    while exists:
        rand_suffix = str(random.randint(100, 999))
        invoice_number = f"{prefix}-{rand_suffix}"
        exists = await collection.find_one({"invoice_number": invoice_number})

    return invoice_number


class InvoiceService:

    @staticmethod
    async def create_invoice(invoice_in: InvoiceCreate, user_id: str) -> dict:
        """
        Create a new invoice in 'draft' status.
        - Validates client_id exists.
        - Recomputes grand_total = subtotal + tax_amount server-side.
        - Sets balance_due = grand_total, amount_paid = 0.
        - Auto-generates invoice number.
        - Defaults due_date to 30 days from now if omitted.
        """
        await validate_client_exists(invoice_in.client_id)

        # Server-side recalculation: grand_total is always subtotal + tax
        subtotal = round(invoice_in.subtotal, 2)
        tax_amount = round(invoice_in.tax_amount, 2)
        grand_total = round(subtotal + tax_amount, 2)

        now = datetime.now(timezone.utc)
        due_date = invoice_in.due_date if invoice_in.due_date else now + timedelta(days=30)

        invoice_number = await generate_invoice_number()

        invoice_dict = {
            "invoice_number": invoice_number,
            "client_id": invoice_in.client_id,
            "quotation_id": invoice_in.quotation_id,
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "grand_total": grand_total,
            "amount_paid": 0.0,
            "balance_due": grand_total,
            "due_date": due_date,
            "payment_status": PaymentStatus.DRAFT.value,
            "created_at": now,
            "created_by": user_id
        }

        collection = get_invoices_collection()
        result = await collection.insert_one(invoice_dict)
        invoice_dict["_id"] = result.inserted_id
        return invoice_dict

    @staticmethod
    async def get_invoice(invoice_id: str) -> dict:
        """Retrieve an invoice by its ID."""
        if not ObjectId.is_valid(invoice_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid invoice ID: '{invoice_id}'"
            )

        collection = get_invoices_collection()
        invoice = await collection.find_one({"_id": ObjectId(invoice_id)})
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice with ID '{invoice_id}' not found."
            )

        # Auto-detect overdue status
        invoice = InvoiceService._check_overdue(invoice)
        return invoice

    @staticmethod
    def _check_overdue(invoice: dict) -> dict:
        """
        Checks if a sent or partially-paid invoice has passed its due date
        and updates its status to 'overdue' in-memory.
        """
        current_status = invoice.get("payment_status")
        due_date = invoice.get("due_date")
        now = datetime.now(timezone.utc)

        if current_status in [PaymentStatus.SENT.value, PaymentStatus.PARTIALLY_PAID.value]:
            if due_date and due_date.replace(tzinfo=timezone.utc) < now:
                invoice["payment_status"] = PaymentStatus.OVERDUE.value
        return invoice

    @staticmethod
    async def update_invoice(invoice_id: str, update_in: InvoiceUpdate, user_id: str) -> dict:
        """
        Update invoice financial details.
        Only allowed in 'draft' status. Recalculates grand_total and balance_due server-side.
        """
        invoice = await InvoiceService.get_invoice(invoice_id)
        current_status = invoice.get("payment_status")

        if current_status != PaymentStatus.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot edit invoice in '{current_status}' status. Must be 'draft'."
            )

        update_data = update_in.model_dump(exclude_unset=True)
        if not update_data:
            return invoice

        # Merge with existing values
        subtotal = round(update_data.get("subtotal", invoice["subtotal"]), 2)
        tax_amount = round(update_data.get("tax_amount", invoice["tax_amount"]), 2)
        grand_total = round(subtotal + tax_amount, 2)
        amount_paid = invoice["amount_paid"]
        balance_due = round(grand_total - amount_paid, 2)

        set_fields = {
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "grand_total": grand_total,
            "balance_due": balance_due,
            "updated_at": datetime.now(timezone.utc),
            "updated_by": user_id
        }

        if "due_date" in update_data and update_data["due_date"] is not None:
            set_fields["due_date"] = update_data["due_date"]

        collection = get_invoices_collection()
        await collection.update_one(
            {"_id": ObjectId(invoice_id)},
            {"$set": set_fields}
        )
        return await InvoiceService.get_invoice(invoice_id)

    @staticmethod
    async def change_status(invoice_id: str, new_status: PaymentStatus, user_id: str) -> dict:
        """
        Transition invoice payment status with validation.
        Valid transitions:
          - draft -> sent
          - sent -> paid | partially_paid | overdue
          - partially_paid -> paid | overdue
          - overdue -> paid | partially_paid (when payment is recorded)
        """
        invoice = await InvoiceService.get_invoice(invoice_id)
        current = invoice.get("payment_status")

        valid_transitions = {
            PaymentStatus.DRAFT.value: [PaymentStatus.SENT],
            PaymentStatus.SENT.value: [PaymentStatus.PAID, PaymentStatus.PARTIALLY_PAID, PaymentStatus.OVERDUE],
            PaymentStatus.PARTIALLY_PAID.value: [PaymentStatus.PAID, PaymentStatus.OVERDUE],
            PaymentStatus.OVERDUE.value: [PaymentStatus.PAID, PaymentStatus.PARTIALLY_PAID],
        }

        allowed = valid_transitions.get(current, [])
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from '{current}' to '{new_status}'. Allowed: {[s.value for s in allowed]}."
            )

        collection = get_invoices_collection()
        await collection.update_one(
            {"_id": ObjectId(invoice_id)},
            {
                "$set": {
                    "payment_status": new_status.value,
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": user_id
                }
            }
        )
        return await InvoiceService.get_invoice(invoice_id)

    @staticmethod
    async def record_payment_on_invoice(invoice_id: str, payment_amount: float) -> dict:
        """
        Updates the invoice's amount_paid and balance_due after a payment is recorded.
        Automatically transitions payment_status based on balance:
          - balance_due == 0 -> 'paid'
          - balance_due > 0 -> 'partially_paid'
        Rejects payments exceeding balance_due (no overpayment without explicit flag).
        """
        invoice = await InvoiceService.get_invoice(invoice_id)
        current_status = invoice.get("payment_status")

        if current_status == PaymentStatus.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot record payment on a 'draft' invoice. It must be sent first."
            )

        if current_status == PaymentStatus.PAID.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invoice is already fully paid."
            )

        balance_due = invoice["balance_due"]
        if payment_amount > balance_due:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment amount ({payment_amount}) exceeds balance due ({balance_due}). Overpayment is not allowed without an explicit overpayment flag."
            )

        new_amount_paid = round(invoice["amount_paid"] + payment_amount, 2)
        new_balance_due = round(invoice["grand_total"] - new_amount_paid, 2)

        if new_balance_due <= 0:
            new_status = PaymentStatus.PAID.value
            new_balance_due = 0.0
        else:
            new_status = PaymentStatus.PARTIALLY_PAID.value

        collection = get_invoices_collection()
        await collection.update_one(
            {"_id": ObjectId(invoice_id)},
            {
                "$set": {
                    "amount_paid": new_amount_paid,
                    "balance_due": new_balance_due,
                    "payment_status": new_status,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        return await InvoiceService.get_invoice(invoice_id)

    @staticmethod
    async def delete_invoice(invoice_id: str) -> bool:
        """Delete an invoice. Only allowed for draft invoices."""
        invoice = await InvoiceService.get_invoice(invoice_id)
        if invoice.get("payment_status") != PaymentStatus.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only 'draft' invoices can be deleted."
            )
        collection = get_invoices_collection()
        result = await collection.delete_one({"_id": ObjectId(invoice_id)})
        return result.deleted_count > 0
