"""The only place stock numbers change.

Every change locks the variant row, refuses to go below zero, and writes a
StockMovement. Views, admin and the importer all call these functions instead
of touching Variant.stock directly.
"""

from django.db import transaction

from .models import StockMovement, Variant


class NotEnoughStock(Exception):
    def __init__(self, variant: Variant, requested: int):
        self.variant = variant
        self.requested = requested
        super().__init__(
            f"Only {variant.stock} pair(s) of {variant} left, {requested} requested"
        )


@transaction.atomic
def adjust_stock(
    variant: Variant,
    change: int,
    reason: str,
    *,
    note: str = "",
    order=None,
    user=None,
) -> StockMovement | None:
    """Add (positive) or remove (negative) pairs. Returns the movement, or None if change is 0."""
    if change == 0:
        return None
    locked = Variant.objects.select_for_update().get(pk=variant.pk)
    new_stock = locked.stock + change
    if new_stock < 0:
        raise NotEnoughStock(locked, -change)
    locked.stock = new_stock
    locked.save(update_fields=["stock"])
    variant.stock = new_stock  # keep the caller's object in sync
    return StockMovement.objects.create(
        variant=locked,
        change=change,
        stock_after=new_stock,
        reason=reason,
        note=note[:200],
        order=order,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )


def set_stock(variant: Variant, count: int, reason: str, **kwargs) -> StockMovement | None:
    """Set stock to an exact count (e.g. after counting shelves), logging the difference."""
    if count < 0:
        raise ValueError("Stock cannot be negative")
    current = Variant.objects.only("stock").get(pk=variant.pk).stock
    return adjust_stock(variant, count - current, reason, **kwargs)
