from datetime import date, datetime, timezone
from decimal import Decimal

from django.test import TestCase

from sales.models import Order

from . import services


class LocalDateGroupingTests(TestCase):
    def setUp(self):
        Order.objects.create(
            total=Decimal("123.45"),
            created_at=datetime(2026, 11, 16, 16, 30, tzinfo=timezone.utc),
        )

    def test_daily_series_uses_manila_date(self):
        rows = services.daily_series(date(2026, 11, 17), date(2026, 11, 17))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], date(2026, 11, 17))
        self.assertEqual(rows[0]["value"], Decimal("123.45"))

    def test_sales_reports_use_manila_dates(self):
        expected_buckets = {
            "daily": date(2026, 11, 17),
            "weekly": date(2026, 11, 16),
            "monthly": date(2026, 11, 1),
            "yearly": date(2026, 1, 1),
        }

        for period, expected_bucket in expected_buckets.items():
            with self.subTest(period=period):
                rows = services.sales_report(
                    period, date(2026, 11, 17), date(2026, 11, 17)
                )
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["bucket"].date(), expected_bucket)
                self.assertEqual(rows[0]["total"], Decimal("123.45"))
