"""Placing, paying and cancelling orders. Stock is taken and returned here."""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from catalog.models import StockMovement, Variant
from catalog.stock import adjust_stock

from .models import DeliveryZone, Order, OrderItem


@dataclass
class Line:
    variant: Variant
    quantity: int = 1


@transaction.atomic
def place_order(
    lines: list[Line],
    *,
    customer_name: str,
    phone: str,
    zone: DeliveryZone | None = None,
    address: str = "",
    notes: str = "",
    channel: str = Order.Channel.WEBSITE,
    payment_method: str = Order.PaymentMethod.CASH,
    payment_reference: str = "",
    user=None,
) -> Order:
    """Create the order and take the pairs out of stock in one go.

    Raises catalog.stock.NotEnoughStock (and saves nothing) if any line can't be filled.
    """
    if not lines:
        raise ValueError("An order needs at least one item")

    order = Order.objects.create(
        customer_name=customer_name,
        phone=phone,
        zone=zone,
        address=address,
        notes=notes,
        channel=channel,
        payment_method=payment_method,
        payment_reference=payment_reference,
        payment_status=(
            Order.PaymentStatus.AWAITING
            if payment_method != Order.PaymentMethod.CASH and payment_reference
            else Order.PaymentStatus.UNPAID
        ),
    )
    for line in lines:
        if line.quantity < 1:
            raise ValueError("Quantity must be at least 1")
        variant = line.variant
        adjust_stock(
            variant, -line.quantity, StockMovement.Reason.SALE, order=order, user=user
        )
        OrderItem.objects.create(
            order=order,
            variant=variant,
            product_name=str(variant.product),
            color=variant.color,
            size=variant.size,
            unit_price=variant.price,
            quantity=line.quantity,
        )
    order.recalculate()
    order.save()
    return order


@transaction.atomic
def cancel_order(order: Order, *, user=None) -> Order:
    """Cancel and put every pair back on the shelf. Safe to call twice."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status == Order.Status.CANCELLED:
        return order
    for item in order.items.select_related("variant"):
        adjust_stock(
            item.variant,
            item.quantity,
            StockMovement.Reason.RETURN,
            note=f"Order {order.number} cancelled",
            order=order,
            user=user,
        )
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    return order


def confirm_payment(order: Order) -> Order:
    order.payment_status = Order.PaymentStatus.PAID
    order.paid_at = timezone.now()
    if order.status == Order.Status.NEW:
        order.status = Order.Status.CONFIRMED
    order.save(update_fields=["payment_status", "paid_at", "status", "updated_at"])
    return order
