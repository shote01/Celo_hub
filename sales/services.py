from decimal import Decimal

from django.db import transaction

from celo.utils import require_positive_decimal
from inventory.services import consume_fifo

from .models import Order, OrderItem


@transaction.atomic
def place_order(*, user, order_type, payment_method, customer, lines):
    """lines: list of (product, quantity). Deducts stock FIFO; rolls back everything if any line is short."""
    if not lines:
        raise ValueError("Order must contain at least one line item.")
    order = Order.objects.create(
        order_type=order_type, payment_method=payment_method, customer=customer, created_by=user
    )
    total = Decimal("0")
    for product, qty in lines:
        qty = require_positive_decimal(qty, f"quantity for {product.name}")
        consume_fifo(product, qty)  # raises InsufficientStock -> whole transaction rolls back
        OrderItem.objects.create(order=order, product=product, quantity=qty, unit_price=product.price)
        total += product.price * qty
    order.total = total
    order.save(update_fields=["total"])
    return order
