"""python manage.py seed_demo  - loads sample data like the Figma screens (safe to run once)."""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from finance.models import CashAdvance, Employee, Expense
from inventory.models import Product
from inventory.services import receive_stock
from sales.models import Customer
from sales.services import place_order


class Command(BaseCommand):
    help = "Create demo users, products, stock, employees, expenses and sales."

    def handle(self, *args, **opts):
        if Product.objects.exists():
            self.stdout.write("Data already present - skipping.")
            return
        admin = User.objects.create_superuser("admin", password="celo-admin-123", role="admin", first_name="Marcelo")
        staff = User.objects.create_user("cashier", password="celo-staff-123", role="staff", first_name="Mika")

        today = timezone.localdate()
        spec = [  # name, kind, category, unit, price, cost, reorder, qty, expiry_days
            ("Chicken fillet", "ingredient", "Meat", "kg", 0, 220, 20, 38, 12),
            ("Cheese slices", "ingredient", "Dairy", "packs", 0, 125, 6, 12, 11),
            ("Boba pearls", "ingredient", "Drinks", "kg", 0, 180, 5, 4, 3),
            ("Milk", "ingredient", "Dairy", "L", 0, 65, 10, 7, 2),
            ("Potato fries", "ingredient", "Sides", "kg", 0, 120, 12, 18, 15),
            ("Chicken Burger", "menu", "Burgers", "pcs", 119, 55, 10, 126, None),
            ("Boba Milk Tea", "menu", "Drinks", "L", 89, 35, 10, 90, None),
            ("Loaded Fries", "menu", "Sides", "pcs", 59, 25, 10, 80, None),
        ]
        for name, kind, cat, unit, price, cost, reorder, qty, exp in spec:
            p = Product.objects.create(name=name, kind=kind, category=cat, unit=unit,
                                       price=price, unit_cost=cost, reorder_level=reorder)
            receive_stock(product=p, quantity=qty, expiry_date=today + timedelta(days=exp) if exp else None, user=admin)

        maria = Customer.objects.create(name="Maria Dela Cruz", phone="0917 000 0000")
        burger, tea, fries = (Product.objects.get(name=n) for n in ("Chicken Burger", "Boba Milk Tea", "Loaded Fries"))
        place_order(user=staff, order_type="walk_in", payment_method="cash", customer=None, lines=[(burger, 2)])
        place_order(user=staff, order_type="walk_in", payment_method="gcash", customer=maria, lines=[(tea, 1), (fries, 1)])
        place_order(user=staff, order_type="grabfood", payment_method="online", customer=None, lines=[(burger, 2), (fries, 1)])

        for name, pos, sal, adv in [("Mika Santos", "Cashier", 6000, 500), ("Jules Reyes", "Kitchen", 5500, 0),
                                    ("Ana Cruz", "Service", 5200, 1000)]:
            e = Employee.objects.create(name=name, position=pos, salary=sal)
            if adv:
                CashAdvance.objects.create(employee=e, amount=adv)
        Expense.objects.create(category="utilities", description="Electricity + water", amount=Decimal("4800"))
        Expense.objects.create(category="rent", description="Store rent", amount=Decimal("15000"))
        Expense.objects.create(category="other", description="Supplies", amount=Decimal("1200"))
        self.stdout.write(self.style.SUCCESS("Demo data loaded. Logins: admin / celo-admin-123, cashier / celo-staff-123"))
