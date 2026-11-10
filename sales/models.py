from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Customer(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30, blank=True)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def short_name(self):
        parts = self.name.split()
        return f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else self.name


class Order(models.Model):
    class OrderType(models.TextChoices):
        WALK_IN = "walk_in", "Walk-in"
        GRABFOOD = "grabfood", "GrabFood"
        FOODPANDA = "foodpanda", "Foodpanda"

    class Payment(models.TextChoices):
        CASH = "cash", "Cash"
        GCASH = "gcash", "GCash"
        ONLINE = "online", "Online"

    order_type = models.CharField(max_length=10, choices=OrderType.choices, default=OrderType.WALK_IN)
    payment_method = models.CharField(max_length=10, choices=Payment.choices, default=Payment.CASH)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="orders")

    class Meta:
        ordering = ["-created_at", "-id"]

    @property
    def number(self):
        return 1000 + self.pk

    @property
    def label(self):
        """'Walk-in', 'Maria D.', 'GrabFood' - what the sales list shows next to #number."""
        if self.customer:
            return self.customer.short_name
        return self.get_order_type_display()

    @property
    def summary(self):
        return " · ".join(f"{i.quantity:g}× {i.product.name}" for i in self.items.select_related("product"))

    def __str__(self):
        return f"#{self.number}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("inventory.Product", on_delete=models.PROTECT, related_name="order_items")
    quantity = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # snapshot at time of sale

    @property
    def line_total(self):
        return self.quantity * self.unit_price
