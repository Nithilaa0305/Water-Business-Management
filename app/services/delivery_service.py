"""Delivery route sheets, dispatch tracking, and driver collection service."""

from datetime import date
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.database.models.operations import DeliverySheet, DeliverySheetItem
from app.database.models.customer import Customer, DeliveryRoute
from app.database.models.sales import SalesInvoice
from app.services.audit_service import AuditService
from app.utilities.dates import now_colombo, today_colombo
from app.utilities.currency import format_currency


class DeliveryService:
    @staticmethod
    def generate_sheet_number(session: Session, prefix: str = "DEL-") -> str:
        """Generate unique daily delivery sheet number."""
        date_str = now_colombo().strftime("%Y%m%d")
        pfx = f"{prefix}{date_str}-"
        last = (
            session.query(DeliverySheet)
            .filter(DeliverySheet.sheet_number.like(f"{pfx}%"))
            .order_by(DeliverySheet.id.desc())
            .first()
        )
        seq = 1
        if last:
            try:
                seq = int(last.sheet_number.split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f"{pfx}{seq:03d}"

    @staticmethod
    def create_delivery_sheet(
        session: Session,
        delivery_date: Optional[date] = None,
        route_id: Optional[int] = None,
        driver_name: Optional[str] = None,
        vehicle_number: Optional[str] = None,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> DeliverySheet:
        """Create a new delivery route dispatch sheet."""
        d_date = delivery_date or today_colombo()
        sheet_num = DeliveryService.generate_sheet_number(session)

        sheet = DeliverySheet(
            sheet_number=sheet_num,
            delivery_date=d_date,
            route_id=route_id,
            driver_name=driver_name,
            vehicle_number=vehicle_number,
            status="PENDING",
            notes=notes,
            user_id=user_id
        )
        session.add(sheet)
        session.flush()

        AuditService.log_action(
            session=session,
            action_type="DELIVERY_SHEET_CREATE",
            entity_name="DeliverySheet",
            entity_id=sheet.id,
            reference_no=sheet.sheet_number,
            new_values={"date": str(d_date), "route_id": route_id, "driver": driver_name},
            reason="Delivery sheet created",
            user_id=user_id
        )
        return sheet

    @staticmethod
    def add_delivery_item(
        session: Session,
        sheet_id: int,
        customer_id: int,
        invoice_id: Optional[int] = None,
        stop_number: int = 1,
        full_19l_delivered: int = 0,
        empty_19l_collected: int = 0,
        payment_collected_cents: int = 0,
        payment_method: str = "CASH",
        notes: Optional[str] = None
    ) -> DeliverySheetItem:
        """
        Add a stop/customer to the delivery sheet.
        Note: If linked to an invoice (invoice_id), stock and revenue are already recorded
        by SalesService to strictly prevent double-counting inventory reductions.
        """
        sheet = session.query(DeliverySheet).filter_by(id=sheet_id).first()
        if not sheet:
            raise ValueError(f"Delivery Sheet #{sheet_id} not found.")

        customer = session.query(Customer).filter_by(id=customer_id).first()
        if not customer:
            raise ValueError(f"Customer #{customer_id} not found.")

        # If invoice_id provided, autofill planned quantities if not explicitly passed
        if invoice_id:
            inv = session.query(SalesInvoice).filter_by(id=invoice_id).first()
            if inv:
                if full_19l_delivered == 0:
                    full_19l_delivered = inv.bottles_delivered_19l or 0
                if empty_19l_collected == 0:
                    empty_19l_collected = inv.bottles_returned_19l or 0
                if payment_collected_cents == 0:
                    payment_collected_cents = inv.amount_paid_cents or 0

        item = DeliverySheetItem(
            sheet_id=sheet_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            stop_number=stop_number,
            status="PENDING",
            full_19l_delivered=full_19l_delivered,
            empty_19l_collected=empty_19l_collected,
            payment_collected_cents=payment_collected_cents,
            payment_method=payment_method,
            notes=notes
        )
        session.add(item)
        session.flush()
        return item

    @staticmethod
    def update_item_status(
        session: Session,
        item_id: int,
        status: str,  # 'DELIVERED', 'PENDING', 'CANCELLED', 'RESCHEDULED'
        actual_full_delivered: Optional[int] = None,
        actual_empty_collected: Optional[int] = None,
        actual_payment_cents: Optional[int] = None,
        notes: Optional[str] = None
    ) -> DeliverySheetItem:
        """Update fulfillment status of a delivery stop."""
        item = session.query(DeliverySheetItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"Delivery sheet item #{item_id} not found.")

        item.status = status
        if actual_full_delivered is not None:
            item.full_19l_delivered = actual_full_delivered
        if actual_empty_collected is not None:
            item.empty_19l_collected = actual_empty_collected
        if actual_payment_cents is not None:
            item.payment_collected_cents = actual_payment_cents
        if notes:
            item.notes = notes

        session.flush()
        return item

    @staticmethod
    def get_sheet_details(session: Session, sheet_id: int) -> Dict[str, Any]:
        """Fetch delivery sheet with all stops, customer details, and totals."""
        sheet = session.query(DeliverySheet).filter_by(id=sheet_id).first()
        if not sheet:
            raise ValueError(f"Delivery sheet #{sheet_id} not found.")

        route_name = "Unassigned Route"
        if sheet.route_id:
            route = session.query(DeliveryRoute).filter_by(id=sheet.route_id).first()
            if route:
                route_name = route.name

        items_data = []
        tot_full = 0
        tot_empty = 0
        tot_cash = 0

        for it in sorted(sheet.items, key=lambda x: x.stop_number):
            cust = it.customer
            tot_full += it.full_19l_delivered
            tot_empty += it.empty_19l_collected
            tot_cash += it.payment_collected_cents

            items_data.append({
                "id": it.id,
                "stop_number": it.stop_number,
                "customer_name": cust.name if cust else "Unknown",
                "customer_phone": cust.phone if cust else "",
                "customer_address": cust.address if cust else "",
                "invoice_number": it.invoice.invoice_number if it.invoice else "Direct/Unbilled",
                "status": it.status,
                "full_19l": it.full_19l_delivered,
                "empty_19l": it.empty_19l_collected,
                "payment_cents": it.payment_collected_cents,
                "payment_display": format_currency(it.payment_collected_cents),
                "notes": it.notes or "",
            })

        return {
            "id": sheet.id,
            "sheet_number": sheet.sheet_number,
            "delivery_date": sheet.delivery_date.strftime("%Y-%m-%d"),
            "route_name": route_name,
            "driver_name": sheet.driver_name or "N/A",
            "vehicle_number": sheet.vehicle_number or "N/A",
            "status": sheet.status,
            "total_stops": len(sheet.items),
            "total_full_19l": tot_full,
            "total_empty_19l": tot_empty,
            "total_cash_collected_cents": tot_cash,
            "total_cash_display": format_currency(tot_cash),
            "items": items_data,
        }

    @staticmethod
    def generate_sheet_text(session: Session, sheet_id: int) -> str:
        """Generate printable ASCII / thermal delivery run sheet."""
        data = DeliveryService.get_sheet_details(session, sheet_id)
        lines = [
            "================================================================",
            "             WATER BUSINESS MANAGER — DELIVERY RUN SHEET        ",
            "================================================================",
            f"Sheet Number:   {data['sheet_number']}",
            f"Delivery Date:  {data['delivery_date']}",
            f"Route / Area:   {data['route_name']}",
            f"Driver:         {data['driver_name']}    Vehicle: {data['vehicle_number']}",
            "----------------------------------------------------------------",
            f"{'Stop':<5} {'Customer':<20} {'Address / Phone':<22} {'Full':<5} {'Empty':<5} {'Collect':>8}",
            "----------------------------------------------------------------",
        ]
        for it in data["items"]:
            addr_phone = f"{it['customer_phone']} {it['customer_address']}"[:20]
            lines.append(
                f"{it['stop_number']:<5} {it['customer_name'][:18]:<20} {addr_phone:<22} "
                f"{it['full_19l']:<5} {it['empty_19l']:<5} {it['payment_display']:>8}"
            )
        lines.extend([
            "----------------------------------------------------------------",
            f"TOTALS: Stops: {data['total_stops']} | Full: {data['total_full_19l']} | Empty: {data['total_empty_19l']} | Cash: {data['total_cash_display']}",
            "================================================================",
            "Driver Signature: __________________   Supervisor: ________________"
        ])
        return "\n".join(lines)
