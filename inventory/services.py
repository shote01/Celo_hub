"""All stock movements go through here so FIFO is enforced in one place."""
from decimal import Decimal

from django.db import transaction

from celo.utils import require_positive_decimal

from .models import StockBatch, WasteRecord


class InsufficientStock(Exception):
    def __init__(self, product, wanted, available):
        self.product, self.wanted, self.available = product, wanted, available
        super().__init__(
            f"Not enough {product.name}: need {wanted} {product.unit}, only {available} on hand."
        )


@transaction.atomic
def receive_stock(*, product, quantity, expiry_date=None, user=None):
    quantity = require_positive_decimal(quantity, "quantity")
    return StockBatch.objects.create(
        product=product, received_qty=quantity, remaining_qty=quantity,
        expiry_date=expiry_date, received_by=user,
    )


@transaction.atomic
def consume_fifo(product, quantity):
    """Take `quantity` from the oldest / soonest-expiring batches. Raises InsufficientStock."""
    quantity = require_positive_decimal(quantity, "quantity")
    batches = list(product.batches_in_stock().select_for_update())
    available = sum((b.remaining_qty for b in batches), Decimal("0"))
    if available < quantity:
        raise InsufficientStock(product, quantity, available)

    left = quantity
    for batch in batches:
        take = min(batch.remaining_qty, left)
        batch.remaining_qty -= take
        batch.save(update_fields=["remaining_qty"])
        left -= take
        if left <= 0:
            break


@transaction.atomic
def record_waste(*, product, quantity, reason, note="", user=None):
    """Remove wasted stock (FIFO) and store its cost so reports can deduct it from revenue."""
    quantity = require_positive_decimal(quantity, "quantity")
    consume_fifo(product, quantity)
    return WasteRecord.objects.create(
        product=product, quantity=quantity, reason=reason, note=note,
        cost=(product.unit_cost * quantity).quantize(Decimal("0.01")), recorded_by=user,
    )
