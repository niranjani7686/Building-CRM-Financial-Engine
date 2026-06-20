import os
import random
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from fastapi import HTTPException, status
from typing import List, Optional
from app.database import get_quotations_collection, get_invoices_collection, Database
from app.models.quotation_model import QuotationCreate, QuotationUpdate, QuotationStatus, LineItem
from app.services.proposal_service import validate_client_exists

async def generate_quotation_number() -> str:
    """
    Generates a unique quotation number with the format: QT-YYYYMMDD-XXX
    Where XXX is a daily sequential counter or a fallback random suffix.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    prefix = f"QT-{date_str}"
    
    collection = get_quotations_collection()
    # Find matching quotations created today
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    end_of_day = start_of_day + timedelta(days=1)
    
    count = await collection.count_documents({
        "created_at": {
            "$gte": start_of_day,
            "$lt": end_of_day
        }
    })
    
    seq_number = str(count + 1).zfill(3)
    # Check uniqueness
    quotation_number = f"{prefix}-{seq_number}"
    exists = await collection.find_one({"quotation_number": quotation_number})
    while exists:
        # Fallback to random if duplicate exists due to concurrency
        rand_suffix = str(random.randint(100, 999))
        quotation_number = f"{prefix}-{rand_suffix}"
        exists = await collection.find_one({"quotation_number": quotation_number})
        
    return quotation_number

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

class QuotationService:
    @staticmethod
    def calculate_quotation_totals(line_items: List[LineItem], discount_percentage: float, tax_rate: float) -> dict:
        """
        Computes all financial calculations server-side.
        Returns subtotal, discount_amount, tax_amount, and grand_total.
        """
        subtotal = 0.0
        calculated_items = []
        
        for item in line_items:
            # Recompute total for each line item
            item_total = round(item.quantity * item.unit_price, 2)
            item.total = item_total
            subtotal += item_total
            calculated_items.append(item)
            
        subtotal = round(subtotal, 2)
        discount_amount = round(subtotal * (discount_percentage / 100.0), 2)
        taxable_amount = round(subtotal - discount_amount, 2)
        tax_amount = round(taxable_amount * tax_rate, 2)
        grand_total = round(taxable_amount + tax_amount, 2)
        
        return {
            "line_items": [item.model_dump() for item in calculated_items],
            "subtotal": subtotal,
            "discount_amount": discount_amount,
            "tax_amount": tax_amount,
            "grand_total": grand_total
        }

    @staticmethod
    async def create_quotation(quotation_in: QuotationCreate, user_id: str) -> dict:
        """Create a new quotation in draft status, calculating all pricing server-side."""
        # 1. Validate client exists
        await validate_client_exists(quotation_in.client_id)

        # 2. Recompute all pricing values
        totals = QuotationService.calculate_quotation_totals(
            quotation_in.line_items,
            quotation_in.discount_percentage,
            quotation_in.tax_rate
        )

        # 3. Generate unique quotation number
        quotation_number = await generate_quotation_number()

        # 4. Save document
        now = datetime.now(timezone.utc)
        quotation_dict = {
            "client_id": quotation_in.client_id,
            "quotation_number": quotation_number,
            "line_items": totals["line_items"],
            "subtotal": totals["subtotal"],
            "discount_amount": totals["discount_amount"],
            "tax_amount": totals["tax_amount"],
            "grand_total": totals["grand_total"],
            "status": QuotationStatus.DRAFT.value,
            "created_at": now,
            "created_by": user_id
        }

        collection = get_quotations_collection()
        result = await collection.insert_one(quotation_dict)
        quotation_dict["_id"] = result.inserted_id
        return quotation_dict

    @staticmethod
    async def get_quotation(quotation_id: str) -> dict:
        """Retrieve a quotation by ID."""
        if not ObjectId.is_valid(quotation_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid quotation ID: '{quotation_id}'"
            )
            
        collection = get_quotations_collection()
        quotation = await collection.find_one({"_id": ObjectId(quotation_id)})
        if not quotation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quotation with ID '{quotation_id}' not found."
            )
        return quotation

    @staticmethod
    async def update_quotation(quotation_id: str, update_in: QuotationUpdate, user_id: str) -> dict:
        """
        Update quotation line items, discounts or tax rates.
        Calculations are completely recomputed server-side.
        Edits only allowed in 'draft' or 'sent' status.
        """
        quotation = await QuotationService.get_quotation(quotation_id)
        current_status = quotation.get("status")

        if current_status in [QuotationStatus.APPROVED.value, QuotationStatus.REJECTED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot edit quotation in '{current_status}' status. It must be in 'draft' or 'sent'."
            )

        # Merge update details
        line_items = update_in.line_items
        if line_items is None:
            # Build LineItem objects from current dict
            line_items = [LineItem(**item) for item in quotation["line_items"]]

        discount_percentage = update_in.discount_percentage
        if discount_percentage is None:
            # Try to retrieve existing discount percentage from fields.
            # If not explicitly stored, derive from amount / subtotal.
            subtotal = quotation["subtotal"]
            discount_amount = quotation["discount_amount"]
            discount_percentage = (discount_amount / subtotal * 100.0) if subtotal > 0 else 0.0

        tax_rate = update_in.tax_rate
        if tax_rate is None:
            subtotal = quotation["subtotal"]
            discount_amount = quotation["discount_amount"]
            taxable_amount = subtotal - discount_amount
            tax_amount = quotation["tax_amount"]
            tax_rate = (tax_amount / taxable_amount) if taxable_amount > 0 else 0.0

        # Recalculate
        totals = QuotationService.calculate_quotation_totals(line_items, discount_percentage, tax_rate)

        collection = get_quotations_collection()
        await collection.update_one(
            {"_id": ObjectId(quotation_id)},
            {
                "$set": {
                    "line_items": totals["line_items"],
                    "subtotal": totals["subtotal"],
                    "discount_amount": totals["discount_amount"],
                    "tax_amount": totals["tax_amount"],
                    "grand_total": totals["grand_total"],
                    "updated_by": user_id,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        return await QuotationService.get_quotation(quotation_id)

    @staticmethod
    async def change_status(quotation_id: str, new_status: QuotationStatus, user_id: str) -> dict:
        """Enforce transition rules: draft -> sent, sent -> approved/rejected."""
        quotation = await QuotationService.get_quotation(quotation_id)
        current_status = quotation.get("status")

        valid = False
        if current_status == QuotationStatus.DRAFT.value and new_status == QuotationStatus.SENT:
            valid = True
        elif current_status == QuotationStatus.SENT.value and new_status in [QuotationStatus.APPROVED, QuotationStatus.REJECTED]:
            valid = True

        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from '{current_status}' to '{new_status}'."
            )

        collection = get_quotations_collection()
        await collection.update_one(
            {"_id": ObjectId(quotation_id)},
            {
                "$set": {
                    "status": new_status.value,
                    "updated_by": user_id,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        return await QuotationService.get_quotation(quotation_id)

    @staticmethod
    async def delete_quotation(quotation_id: str) -> bool:
        """Delete a quotation document."""
        await QuotationService.get_quotation(quotation_id)
        collection = get_quotations_collection()
        result = await collection.delete_one({"_id": ObjectId(quotation_id)})
        return result.deleted_count > 0

    @staticmethod
    async def convert_to_invoice(quotation_id: str, user_id: str) -> dict:
        """
        Converts an approved quotation into a Draft Invoice.
        Copies client details, totals, and records the quotation ID.
        """
        quotation = await QuotationService.get_quotation(quotation_id)
        if quotation.get("status") != QuotationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot convert quotation to invoice. Quotation must be 'approved' (current status: '{quotation.get('status')}')."
            )

        # Generate unique invoice number
        invoice_number = await generate_invoice_number()
        
        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=30)  # Standard 30 days payment terms
        
        invoice_dict = {
            "invoice_number": invoice_number,
            "client_id": quotation["client_id"],
            "quotation_id": quotation_id,
            "subtotal": quotation["subtotal"],
            "tax_amount": quotation["tax_amount"],
            "grand_total": quotation["grand_total"],
            "amount_paid": 0.0,
            "balance_due": quotation["grand_total"],
            "due_date": due_date,
            "payment_status": "draft",  # Starts in draft status
            "created_at": now,
            "created_by": user_id
        }

        invoices_collection = get_invoices_collection()
        result = await invoices_collection.insert_one(invoice_dict)
        invoice_dict["_id"] = result.inserted_id
        
        # Mark quotation as converted in DB (optional flag)
        quotations_collection = get_quotations_collection()
        await quotations_collection.update_one(
            {"_id": ObjectId(quotation_id)},
            {"$set": {"converted_to_invoice_id": str(result.inserted_id)}}
        )
        
        return invoice_dict
