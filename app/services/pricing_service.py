"""Product price history, packaging unit calculations, and customer-specific pricing service."""

from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.database.models.product import Product, PackagingUnit, ProductPriceHistory
from app.database.models.customer import CustomerPrice
from app.services.audit_service import AuditService
from app.utilities.dates import now_colombo
from app.utilities.currency import format_currency


class PricingService:
    @staticmethod
    def calculate_packaging_pricing(
        unit_price_cents: int,
        unit_factor: int = 1,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """
        Calculate packaging unit pricing breakdown distinguishing between:
        - Price per pack / case
        - Number of bottles per pack / case (factor)
        - Equivalent individual bottle price
        - Total line price and total physical bottles
        """
        factor = max(1, unit_factor)
        qty = max(0, quantity)
        equiv_bottle_price = unit_price_cents // factor
        line_total_cents = unit_price_cents * qty
        total_bottles = qty * factor

        return {
            "unit_price_cents": unit_price_cents,
            "unit_price_display": format_currency(unit_price_cents),
            "unit_factor": factor,
            "quantity": qty,
            "total_bottles": total_bottles,
            "equivalent_bottle_price_cents": equiv_bottle_price,
            "equivalent_bottle_price_display": format_currency(equiv_bottle_price),
            "line_total_cents": line_total_cents,
            "line_total_display": format_currency(line_total_cents),
        }

    @staticmethod
    def record_price_change(
        session: Session,
        product_id: int,
        price_type: str,  # 'SELLING' or 'BUYING'
        old_price_cents: int,
        new_price_cents: int,
        packaging_unit_id: Optional[int] = None,
        batch_id: Optional[int] = None,
        user_id: Optional[int] = None,
        reason: Optional[str] = None
    ) -> ProductPriceHistory:
        """
        Record every price change in ProductPriceHistory with complete audit trail.
        Stores packaging unit, factor, and calculated equivalent individual bottle price.
        """
        product = session.query(Product).filter_by(id=product_id).first()
        if not product:
            raise ValueError(f"Product #{product_id} not found.")

        factor = 1
        if packaging_unit_id:
            pkg = session.query(PackagingUnit).filter_by(id=packaging_unit_id).first()
            if pkg:
                factor = max(1, pkg.factor)

        equiv_bottle_price = new_price_cents // factor

        history_entry = ProductPriceHistory(
            product_id=product_id,
            batch_id=batch_id,
            packaging_unit_id=packaging_unit_id,
            unit_factor=factor,
            price_type=price_type.upper(),
            old_price_cents=old_price_cents,
            new_price_cents=new_price_cents,
            equivalent_bottle_price_cents=equiv_bottle_price,
            effective_date=now_colombo(),
            user_id=user_id,
            reason=reason or f"{price_type.capitalize()} price update"
        )
        session.add(history_entry)
        session.flush()

        # Update product's default selling price if base unit selling price changed
        if price_type.upper() == "SELLING" and (not packaging_unit_id or factor == 1):
            product.default_selling_price_cents = new_price_cents

        AuditService.log_action(
            session=session,
            action_type="PRICE_CHANGE",
            entity_name="ProductPriceHistory",
            entity_id=history_entry.id,
            reference_no=product.code,
            old_values={"price_cents": old_price_cents},
            new_values={
                "price_cents": new_price_cents,
                "equivalent_bottle_cents": equiv_bottle_price,
                "unit_factor": factor,
                "type": price_type
            },
            reason=reason or "Price changed",
            user_id=user_id
        )
        return history_entry

    @staticmethod
    def get_effective_customer_price(
        session: Session,
        customer_id: Optional[int],
        product_id: int,
        packaging_unit_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Determine effective price for a customer and packaging unit.
        Checks for customer-specific price first, falls back to product default.
        Returns price per unit and equivalent price per bottle.
        """
        product = session.query(Product).filter_by(id=product_id).first()
        if not product:
            raise ValueError(f"Product #{product_id} not found.")

        factor = 1
        pkg_name = "Bottle"
        if packaging_unit_id:
            pkg = session.query(PackagingUnit).filter_by(id=packaging_unit_id).first()
            if pkg:
                factor = max(1, pkg.factor)
                pkg_name = pkg.name

        # Check customer special price
        special_price = None
        if customer_id:
            # First check special price matching specific packaging unit
            special_price = (
                session.query(CustomerPrice)
                .filter_by(customer_id=customer_id, product_id=product_id, packaging_unit_id=packaging_unit_id)
                .first()
            )
            # If not found and packaging_unit_id is set, check base unit special price
            if not special_price and packaging_unit_id:
                base_special = (
                    session.query(CustomerPrice)
                    .filter_by(customer_id=customer_id, product_id=product_id, packaging_unit_id=None)
                    .first()
                )
                if base_special:
                    # Scale base special price by factor
                    agreed_cents = base_special.agreed_price_cents * factor
                    return {
                        "price_cents": agreed_cents,
                        "price_display": format_currency(agreed_cents),
                        "unit_factor": factor,
                        "packaging_name": pkg_name,
                        "equivalent_bottle_price_cents": base_special.agreed_price_cents,
                        "equivalent_bottle_price_display": format_currency(base_special.agreed_price_cents),
                        "is_special_price": True,
                    }

        if special_price:
            agreed_cents = special_price.agreed_price_cents
            equiv_bottle_price = agreed_cents // factor
            return {
                "price_cents": agreed_cents,
                "price_display": format_currency(agreed_cents),
                "unit_factor": factor,
                "packaging_name": pkg_name,
                "equivalent_bottle_price_cents": equiv_bottle_price,
                "equivalent_bottle_price_display": format_currency(equiv_bottle_price),
                "is_special_price": True,
            }

        # Fallback to product default selling price
        base_price_cents = product.default_selling_price_cents
        unit_price_cents = base_price_cents * factor
        return {
            "price_cents": unit_price_cents,
            "price_display": format_currency(unit_price_cents),
            "unit_factor": factor,
            "packaging_name": pkg_name,
            "equivalent_bottle_price_cents": base_price_cents,
            "equivalent_bottle_price_display": format_currency(base_price_cents),
            "is_special_price": False,
        }

    @staticmethod
    def get_price_history_report(
        session: Session,
        product_id: Optional[int] = None,
        price_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Query and format price change history for reports and UI displays."""
        q = session.query(ProductPriceHistory).order_by(ProductPriceHistory.effective_date.desc(), ProductPriceHistory.id.desc())
        if product_id:
            q = q.filter(ProductPriceHistory.product_id == product_id)
        if price_type:
            q = q.filter(ProductPriceHistory.price_type == price_type.upper())

        records = q.limit(limit).all()
        result = []
        for r in records:
            prod_name = r.product.name if r.product else "Unknown Product"
            prod_code = r.product.code if r.product else ""
            pkg_name = r.packaging_unit.name if r.packaging_unit else "Bottle"
            result.append({
                "id": r.id,
                "date": r.effective_date.strftime("%Y-%m-%d %H:%M"),
                "product_code": prod_code,
                "product_name": prod_name,
                "packaging_unit": pkg_name,
                "unit_factor": r.unit_factor,
                "price_type": r.price_type,
                "old_price_cents": r.old_price_cents,
                "old_price_display": format_currency(r.old_price_cents),
                "new_price_cents": r.new_price_cents,
                "new_price_display": format_currency(r.new_price_cents),
                "equivalent_bottle_price_cents": r.equivalent_bottle_price_cents,
                "equivalent_bottle_price_display": format_currency(r.equivalent_bottle_price_cents or (r.new_price_cents // max(1, r.unit_factor))),
                "user_id": r.user_id,
                "reason": r.reason or "",
            })
        return result
