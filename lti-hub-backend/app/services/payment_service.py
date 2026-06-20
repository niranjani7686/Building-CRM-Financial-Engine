from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException, status
from typing import List, Optional
from app.database import get_payments_collection, get_invoices_collection
from app.models.payment_model import RecordPayment, PaymentStatusEnum, PaymentMethodEnum
from app.services.invoice_service import InvoiceService
from app.services.proposal_service import validate_client_exists


class PaymentService:

    @staticmethod
    async def record_payment(payment_in: RecordPayment, user_id: str) -> dict:
        """
        Records a payment against an invoice.
        - Validates that the invoice exists and belongs to the specified client.
        - Validates that the payment amount does not exceed the invoice balance_due.
        - Updates the invoice's amount_paid, balance_due, and payment_status.
        - Creates a payment record in the p5_payments collection.
        """
        # 1. Validate client exists
        await validate_client_exists(payment_in.client_id)

        # 2. Validate invoice exists and belongs to the client
        invoice = await InvoiceService.get_invoice(payment_in.invoice_id)
        if invoice["client_id"] != payment_in.client_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invoice '{payment_in.invoice_id}' does not belong to client '{payment_in.client_id}'."
            )

        # 3. Validate financial integrity: no payment on draft, no overpayment
        payment_status = invoice.get("payment_status")
        if payment_status == "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot record payment on a 'draft' invoice. It must be sent first."
            )
        if payment_status == "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invoice is already fully paid."
            )

        balance_due = invoice["balance_due"]
        if payment_in.payment_amount > balance_due:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment amount ({payment_in.payment_amount}) exceeds outstanding balance ({balance_due}). Overpayment not allowed."
            )

        # 4. Create payment record
        now = datetime.now(timezone.utc)
        payment_date = payment_in.payment_date if payment_in.payment_date else now

        payment_dict = {
            "invoice_id": payment_in.invoice_id,
            "client_id": payment_in.client_id,
            "payment_amount": round(payment_in.payment_amount, 2),
            "payment_date": payment_date,
            "payment_method": payment_in.payment_method.value,
            "reference_number": payment_in.reference_number,
            "status": PaymentStatusEnum.PENDING.value,
            "created_at": now,
            "recorded_by": user_id
        }

        collection = get_payments_collection()
        result = await collection.insert_one(payment_dict)
        payment_dict["_id"] = result.inserted_id

        # 5. Update invoice balance via the invoice service
        await InvoiceService.record_payment_on_invoice(
            payment_in.invoice_id,
            payment_in.payment_amount
        )

        return payment_dict

    @staticmethod
    async def get_payment(payment_id: str) -> dict:
        """Retrieve a single payment by its ID."""
        if not ObjectId.is_valid(payment_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid payment ID: '{payment_id}'"
            )

        collection = get_payments_collection()
        payment = await collection.find_one({"_id": ObjectId(payment_id)})
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with ID '{payment_id}' not found."
            )
        return payment

    @staticmethod
    async def verify_payment(payment_id: str, user_id: str) -> dict:
        """
        Marks a pending payment as verified.
        Only pending payments can be verified.
        """
        payment = await PaymentService.get_payment(payment_id)
        if payment["status"] != PaymentStatusEnum.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment is '{payment['status']}', only 'pending' payments can be verified."
            )

        collection = get_payments_collection()
        await collection.update_one(
            {"_id": ObjectId(payment_id)},
            {
                "$set": {
                    "status": PaymentStatusEnum.VERIFIED.value,
                    "verified_by": user_id,
                    "verified_at": datetime.now(timezone.utc)
                }
            }
        )
        return await PaymentService.get_payment(payment_id)

    @staticmethod
    async def get_payment_history_by_invoice(invoice_id: str) -> List[dict]:
        """Retrieve all payments for a specific invoice, ordered by payment_date descending."""
        if not ObjectId.is_valid(invoice_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid invoice ID: '{invoice_id}'"
            )

        collection = get_payments_collection()
        cursor = collection.find({"invoice_id": invoice_id}).sort("payment_date", -1)
        payments = await cursor.to_list(length=500)
        return payments

    @staticmethod
    async def get_payment_history_by_client(client_id: str) -> List[dict]:
        """Retrieve all payments for a specific client, ordered by payment_date descending."""
        if not ObjectId.is_valid(client_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid client ID: '{client_id}'"
            )

        collection = get_payments_collection()
        cursor = collection.find({"client_id": client_id}).sort("payment_date", -1)
        payments = await cursor.to_list(length=500)
        return payments

    @staticmethod
    async def get_outstanding_balances(client_id: Optional[str] = None) -> List[dict]:
        """
        Returns all invoices with outstanding balances (balance_due > 0).
        Optionally filtered by client_id.
        """
        invoices_collection = get_invoices_collection()
        query = {"balance_due": {"$gt": 0}}
        if client_id:
            query["client_id"] = client_id

        cursor = invoices_collection.find(
            query,
            {
                "_id": 1,
                "invoice_number": 1,
                "client_id": 1,
                "grand_total": 1,
                "amount_paid": 1,
                "balance_due": 1,
                "due_date": 1,
                "payment_status": 1
            }
        ).sort("due_date", 1)

        invoices = await cursor.to_list(length=500)
        # Convert ObjectId to string for JSON serialization
        for inv in invoices:
            inv["_id"] = str(inv["_id"])
        return invoices

    @staticmethod
    async def get_overdue_invoices(client_id: Optional[str] = None) -> List[dict]:
        """
        Returns all invoices that are past due_date and have outstanding balance.
        """
        now = datetime.now(timezone.utc)
        invoices_collection = get_invoices_collection()
        query = {
            "balance_due": {"$gt": 0},
            "due_date": {"$lt": now},
            "payment_status": {"$nin": ["draft", "paid"]}
        }
        if client_id:
            query["client_id"] = client_id

        cursor = invoices_collection.find(
            query,
            {
                "_id": 1,
                "invoice_number": 1,
                "client_id": 1,
                "grand_total": 1,
                "amount_paid": 1,
                "balance_due": 1,
                "due_date": 1,
                "payment_status": 1
            }
        ).sort("due_date", 1)

        invoices = await cursor.to_list(length=500)
        for inv in invoices:
            inv["_id"] = str(inv["_id"])
        return invoices
