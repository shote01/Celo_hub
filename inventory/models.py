from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone


class Product(models.Model):
    """An ingredient (raw stock) or a menu item (sold to customers)."""

    class Kind(models.TextChoices):
        INGREDIENT = "ingredient", "Ingredient"
        MENU = "menu", "Menu"

    class Unit(models.TextChoices):
        PCS = "pcs", "pcs"
        KG = "kg", "kg"
        G = "g", "g"
        L = "L", "L"
        ML = "mL", "mL"
        PACKS = "packs", "packs"

    name = models.CharField(max_length=120, unique=True)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.INGREDIENT)
    category = models.CharField(max_length=60, blank=True, help_text="e.g. Drinks, Burgers, Dairy")
    unit = models.CharField(max_length=8, choices=Unit.choices, default=Unit.PCS)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)],
        help_text="Selling price (menu items only).",
    )
    unit_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)],
        help_text="What one unit costs Celo; used to value waste.",
    )
    reorder_level = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    # ---- stock helpers ---------
    def batches_in_stock(self):
        """Batches with stock left, in FIFO order: soonest expiry, then oldest received."""
        return (
            self.batches.filter(remaining_qty__gt=0)
            .order_by(F("expiry_date").asc(nulls_last=True), "received_at", "id")
        )

    @property
    def on_hand(self):
        return self.batches.aggregate(t=Sum("remaining_qty"))["t"] or Decimal("0")

    @property
    def next_expiry(self):
        batch = self.batches_in_stock().exclude(expiry_date__isnull=True).first()
        return batch.expiry_date if batch else None

    @property
    def status(self):
        """'Use first' when a batch is expired/near expiry, 'Low' under reorder level, else 'Fresh'."""
        expiry = self.next_expiry
        warn = timezone.localdate() + timedelta(days=settings.CELO_FIFO_WARNING_DAYS)
        if expiry and expiry <= warn:
            return "Use first"
        if self.reorder_level and self.on_hand <= self.reorder_level:
            return "Low"
        return "Fresh"


class StockBatch(models.Model):
    """One delivery of a product. Each batch is consumed oldest/soonest-expiry first."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="batches")
    received_qty = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    remaining_qty = models.DecimalField(max_digits=10, decimal_places=2)
    expiry_date = models.DateField(null=True, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["received_at"]
        verbose_name_plural = "stock batches"

    def __str__(self):
        return f"{self.product} batch #{self.pk}"

    @property
    def is_expired(self):
        return bool(self.expiry_date and self.expiry_date < timezone.localdate())


class WasteRecord(models.Model):
    """Spoiled ingredients or mistakenly prepared orders. Cost is snapshotted."""

    class Reason(models.TextChoices):
        SPOILED = "spoiled", "Spoiled / expired"
        ORDER_ERROR = "order_error", "Order error"
        OTHER = "other", "Other"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="waste_records")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    reason = models.CharField(max_length=12, choices=Reason.choices, default=Reason.SPOILED)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.CharField(max_length=200, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.quantity} {self.product.unit} {self.product} wasted"
