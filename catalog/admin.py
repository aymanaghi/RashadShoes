from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Sum
from django.utils.html import format_html

from .models import Brand, Category, Product, ProductImage, StockMovement, Variant
from .stock import NotEnoughStock, adjust_stock, set_stock
from .utils import parse_sizes


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "position"]
    list_editable = ["position"]
    prepopulated_fields = {"slug": ["name"]}


class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ["preview", "image", "color", "position"]
    readonly_fields = ["preview"]

    @admin.display(description="")
    def preview(self, obj):
        if obj.pk and obj.image:
            return format_html('<img src="{}" style="height:60px;border-radius:6px">', obj.image.url)
        return ""


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0
    fields = ["color", "size", "stock", "price_override", "sku"]
    readonly_fields = ["sku"]


class ProductForm(forms.ModelForm):
    """Adds a quick way to create many sizes at once: colour + '40-44' + pairs each."""

    quick_color = forms.CharField(
        label="Add colour", required=False, help_text="e.g. Black"
    )
    quick_sizes = forms.CharField(
        label="Sizes", required=False, help_text="e.g. 40-44 or 38, 39, 41"
    )
    quick_qty = forms.IntegerField(
        label="Pairs of each size", required=False, min_value=0, initial=1
    )

    class Meta:
        model = Product
        fields = "__all__"

    def clean(self):
        data = super().clean()
        color, sizes = data.get("quick_color"), data.get("quick_sizes")
        if bool(color) != bool(sizes):
            raise forms.ValidationError("To add sizes quickly, fill in both the colour and the sizes.")
        if sizes:
            try:
                data["quick_size_list"] = parse_sizes(sizes)
            except ValueError as exc:
                self.add_error("quick_sizes", str(exc))
        return data


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    list_display = ["thumb", "__str__", "category", "gender", "price", "pairs", "is_active", "is_featured"]
    list_display_links = ["thumb", "__str__"]
    list_editable = ["price", "is_active", "is_featured"]
    list_filter = ["is_active", "gender", "category", "brand"]
    search_fields = ["name", "brand__name", "variants__sku"]
    autocomplete_fields = ["brand"]
    inlines = [VariantInline, ImageInline]
    fieldsets = [
        (None, {"fields": ["brand", "name", "category", "gender", "price", "compare_at_price", "description"]}),
        ("On the website", {"fields": ["is_active", "is_featured", "slug"]}),
        (
            "Quickly add sizes",
            {
                "fields": ["quick_color", "quick_sizes", "quick_qty"],
                "description": "Creates one row per size below. Existing sizes are skipped.",
            },
        ),
    ]
    readonly_fields = ["slug"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("brand", "category").annotate(
            _pairs=Sum("variants__stock")
        ).prefetch_related("images")

    @admin.display(description="")
    def thumb(self, obj):
        img = obj.main_image
        if img:
            return format_html('<img src="{}" style="height:40px;border-radius:4px">', img.image.url)
        return "—"

    @admin.display(description="Pairs", ordering="_pairs")
    def pairs(self, obj):
        return obj._pairs or 0

    @transaction.atomic
    def save_formset(self, request, form, formset, change):
        if formset.model is not Variant:
            return super().save_formset(request, form, formset, change)

        # Stock edits in the table go through the stock log, never straight to the number.
        variants = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for variant in variants:
            wanted = variant.stock
            if variant.pk is None:
                variant.stock = 0
                variant.save()
                adjust_stock(variant, wanted, StockMovement.Reason.INITIAL, user=request.user)
            else:
                variant.stock = Variant.objects.get(pk=variant.pk).stock
                variant.save()
                set_stock(variant, wanted, StockMovement.Reason.ADJUSTMENT, note="Edited in panel", user=request.user)
        formset.save_m2m()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        sizes = form.cleaned_data.get("quick_size_list")
        if not sizes:
            return
        color = form.cleaned_data["quick_color"].strip().title()
        qty = form.cleaned_data.get("quick_qty") or 0
        created = 0
        for size in sizes:
            variant, is_new = Variant.objects.get_or_create(product=form.instance, color=color, size=size)
            if is_new:
                created += 1
                adjust_stock(variant, qty, StockMovement.Reason.INITIAL, user=request.user)
        self.message_user(request, f"Added {created} size(s) in {color}.", messages.SUCCESS)


class StockLevelFilter(admin.SimpleListFilter):
    title = "stock"
    parameter_name = "level"

    def lookups(self, request, model_admin):
        return [("out", "Sold out"), ("low", "Running low"), ("in", "In stock")]

    def queryset(self, request, queryset):
        threshold = settings.SHOP["LOW_STOCK_THRESHOLD"]
        if self.value() == "out":
            return queryset.filter(stock=0)
        if self.value() == "low":
            return queryset.filter(stock__gt=0, stock__lte=threshold)
        if self.value() == "in":
            return queryset.filter(stock__gt=0)
        return queryset


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    """The stock list: every colour and size, with one-click 'sold' / 'received'."""

    list_display = ["sku", "product", "color", "size", "stock_badge", "price"]
    list_filter = [StockLevelFilter, "product__gender", "product__category", "product__brand", "size"]
    search_fields = ["sku", "product__name", "product__brand__name", "color"]
    list_select_related = ["product", "product__brand"]
    actions = ["sold_one", "received_one"]
    readonly_fields = ["stock"]
    list_per_page = 100

    @admin.display(description="Pairs", ordering="stock")
    def stock_badge(self, obj):
        if obj.stock == 0:
            colour, label = "#b42318", "Sold out"
        elif obj.is_low:
            colour, label = "#b54708", f"{obj.stock} · low"
        else:
            colour, label = "#067647", str(obj.stock)
        return format_html('<b style="color:{}">{}</b>', colour, label)

    @admin.action(description="Sold 1 pair of each selected")
    def sold_one(self, request, queryset):
        done, failed = 0, []
        for variant in queryset:
            try:
                adjust_stock(variant, -1, StockMovement.Reason.SALE, note="Marked sold in panel", user=request.user)
                done += 1
            except NotEnoughStock:
                failed.append(str(variant))
        if done:
            self.message_user(request, f"Took {done} pair(s) out of stock.", messages.SUCCESS)
        if failed:
            self.message_user(request, "Already sold out: " + ", ".join(failed), messages.WARNING)

    @admin.action(description="Received 1 more pair of each selected")
    def received_one(self, request, queryset):
        for variant in queryset:
            adjust_stock(variant, 1, StockMovement.Reason.RESTOCK, user=request.user)
        self.message_user(request, f"Added 1 pair to {queryset.count()} size(s).", messages.SUCCESS)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    """Read-only history: the digital version of the notebook."""

    list_display = ["created_at", "variant", "signed_change", "stock_after", "reason", "order", "created_by", "note"]
    list_filter = ["reason", "created_at"]
    search_fields = ["variant__sku", "variant__product__name", "note", "order__number"]
    list_select_related = ["variant__product__brand", "order", "created_by"]
    date_hierarchy = "created_at"

    @admin.display(description="Change", ordering="change")
    def signed_change(self, obj):
        return f"+{obj.change}" if obj.change > 0 else str(obj.change)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
