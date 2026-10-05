from decimal import Decimal

from django.db import models
from django.utils import timezone

from catalog.models import Variant


class DeliveryZone(models.Model):
    """Area with a flat delivery fee, e.g. Tripoli $3, Beirut $5."""

    name = models.CharField(max_length=80, unique=True)
    fee = models.DecimalField(max_digits=6, decimal_places=2)
    is_active = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return f"{self.name} (${self.fee})"


class Order(models.Model):
    class Channel(models.TextChoices):
        WEBSITE = "website", "Website"
        WHATSAPP = "whatsapp", "WhatsApp"
        INSTAGRAM = "instagram", "Instagram"
        SHOP = "shop", "In the shop"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash on delivery"
        WHISH = "whish", "Whish"
        OMT = "omt", "OMT"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Not paid yet"
        AWAITING = "awaiting", "Customer says sent, check it"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONFIRMED = "confirmed", "Confirmed"
        SHIPPED = "shipped", "Out for delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=20, unique=True, editable=False)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WEBSITE)
    customer_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    zone = models.ForeignKey(
        DeliveryZone, on_delete=models.PROTECT, null=True, blank=True, verbose_name="delivery area"
    )
    address = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    payment_method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    payment_reference = models.CharField(
        max_length=80, blank=True, help_text="Whish / OMT transfer reference the customer gave"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order {self.number}"

    def save(self, *args, **kwargs):
        if not self.number:
            stamp = timezone.localtime().strftime("%y%m%d")
            today = Order.objects.filter(number__startswith=f"R{stamp}").count() + 1
            self.number = f"R{stamp}-{today:03d}"
            while Order.objects.filter(number=self.number).exists():
                today += 1
                self.number = f"R{stamp}-{today:03d}"
        super().save(*args, **kwargs)

    def recalculate(self):
        self.subtotal = sum((item.line_total for item in self.items.all()), Decimal("0"))
        self.delivery_fee = self.zone.fee if self.zone else Decimal("0")
        self.total = self.subtotal + self.delivery_fee


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(Variant, on_delete=models.PROTECT, related_name="order_items")
    # Snapshot of what was sold, so later edits to the product don't rewrite history.
    product_name = models.CharField(max_length=200)
    color = models.CharField(max_length=40)
    size = models.CharField(max_length=10)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} × {self.product_name} {self.color} {self.size}"

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity
