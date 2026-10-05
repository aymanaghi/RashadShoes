from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils.text import slugify


def unique_slug(instance, value: str, field: str = "slug") -> str:
    """Slugify `value`, adding -2, -3... until it is unique for this model."""
    base = slugify(value)[:180] or "item"
    slug = base
    model = type(instance)
    n = 2
    while model.objects.filter(**{field: slug}).exclude(pk=instance.pk).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class Brand(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)


class Category(models.Model):
    """Type of shoe: sneakers, formal, sandals, boots, slippers..."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)


class Gender(models.TextChoices):
    MEN = "men", "Men"
    WOMEN = "women", "Women"
    KIDS = "kids", "Kids"
    UNISEX = "unisex", "Unisex"


class ProductQuerySet(models.QuerySet):
    def visible(self):
        """Products a customer should see: active and with at least one pair in stock."""
        return self.filter(is_active=True, variants__stock__gt=0).distinct()


class Product(models.Model):
    """A shoe model, e.g. 'Air Force 1'. Sizes and colours live on Variant."""

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products")
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products", null=True, blank=True
    )
    gender = models.CharField(max_length=10, choices=Gender.choices, default=Gender.UNISEX)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    compare_at_price = models.DecimalField(
        "price before discount",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional. Shown crossed out when the shoe is on sale.",
    )
    is_active = models.BooleanField("show on website", default=True)
    is_featured = models.BooleanField("feature on home page", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-is_featured", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["brand", "name"], name="unique_model_per_brand"),
        ]

    def __str__(self):
        return f"{self.brand} {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, f"{self.brand.name} {self.name}")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:product", args=[self.slug])

    @property
    def on_sale(self) -> bool:
        return bool(self.compare_at_price and self.compare_at_price > self.price)

    @property
    def total_stock(self) -> int:
        return self.variants.aggregate(total=Sum("stock"))["total"] or 0

    @property
    def main_image(self):
        return self.images.first()


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/%Y/%m/")
    color = models.CharField(
        max_length=40, blank=True, help_text="Optional. Which colour this photo shows."
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"Photo of {self.product}"


def size_sort_key(size: str):
    """Sort '38', '38.5', '39', 'M', 'L' sensibly: numbers first, by value."""
    try:
        return (0, Decimal(size.replace(",", ".")), "")
    except Exception:
        return (1, Decimal(0), size)


class Variant(models.Model):
    """One colour + one size of a product. Stock is counted here, in pairs."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    color = models.CharField(max_length=40)
    size = models.CharField(max_length=10, help_text="EU size, e.g. 42 or 37.5")
    sku = models.CharField("code", max_length=40, unique=True, null=True, blank=True)
    stock = models.PositiveIntegerField("pairs in stock", default=0)
    price_override = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Leave empty to use the product price.",
    )

    class Meta:
        ordering = ["product", "color", "size"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "color", "size"], name="unique_color_size_per_product"
            ),
        ]

    def __str__(self):
        return f"{self.product} · {self.color} · {self.size}"

    def save(self, *args, **kwargs):
        self.color = self.color.strip().title()
        self.size = self.size.strip().replace(",", ".")
        self.sku = (self.sku or "").strip().upper() or None
        super().save(*args, **kwargs)
        if not self.sku:
            # Short code the owner can say on the phone: RS-00042
            self.sku = f"RS-{self.pk:05d}"
            super().save(update_fields=["sku"])

    @property
    def price(self) -> Decimal:
        return self.price_override if self.price_override is not None else self.product.price

    @property
    def is_low(self) -> bool:
        return 0 < self.stock <= settings.SHOP["LOW_STOCK_THRESHOLD"]


class StockMovement(models.Model):
    """Every change to stock, so the shop always knows why a number changed.

    This is what replaces the paper notebook.
    """

    class Reason(models.TextChoices):
        INITIAL = "initial", "First count"
        RESTOCK = "restock", "New delivery"
        SALE = "sale", "Sold"
        RETURN = "return", "Returned / order cancelled"
        ADJUSTMENT = "adjustment", "Correction"

    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name="movements")
    change = models.IntegerField(help_text="+3 for three pairs in, -1 for one pair out")
    stock_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    note = models.CharField(max_length=200, blank=True)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="movements"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        sign = "+" if self.change > 0 else ""
        return f"{sign}{self.change} {self.variant} ({self.get_reason_display()})"
