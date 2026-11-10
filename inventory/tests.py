from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from . import services
from .models import Product


class FifoTests(TestCase):
    def setUp(self):
        self.p = Product.objects.create(name="Milk", unit="L", unit_cost=60)
        today = timezone.localdate()
        self.late = services.receive_stock(product=self.p, quantity=10, expiry_date=today + timedelta(days=20))
        self.soon = services.receive_stock(product=self.p, quantity=5, expiry_date=today + timedelta(days=2))

    def test_consumes_soonest_expiry_first(self):
        services.consume_fifo(self.p, 7)
        self.soon.refresh_from_db(); self.late.refresh_from_db()
        self.assertEqual(self.soon.remaining_qty, 0)
        self.assertEqual(self.late.remaining_qty, Decimal("8"))

    def test_insufficient_stock_changes_nothing(self):
        with self.assertRaises(services.InsufficientStock):
            services.consume_fifo(self.p, 99)
        self.assertEqual(self.p.on_hand, 15)

    def test_waste_records_cost_and_deducts(self):
        w = services.record_waste(product=self.p, quantity=2, reason="spoiled")
        self.assertEqual(w.cost, Decimal("120.00"))
        self.assertEqual(self.p.on_hand, 13)

    def test_rejects_non_positive_quantity(self):
        with self.assertRaisesMessage(ValueError, "quantity must be greater than zero."):
            services.receive_stock(product=self.p, quantity=0)
        with self.assertRaisesMessage(ValueError, "quantity must be greater than zero."):
            services.consume_fifo(self.p, -1)
        with self.assertRaisesMessage(ValueError, "quantity must be greater than zero."):
            services.record_waste(product=self.p, quantity=0, reason="spoiled")
