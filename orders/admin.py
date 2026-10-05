from django.contrib import admin, messages

from .models import DeliveryZone, Order, OrderItem
from .services import cancel_order, confirm_payment


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ["name", "fee", "is_active", "position"]
    list_editable = ["fee", "is_active", "position"]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ["product_name", "color", "size", "quantity", "unit_price"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "number", "created_at", "customer_name", "phone", "zone", "total",
        "payment_method", "payment_status", "status", "channel",
    ]
    list_filter = ["status", "payment_status", "payment_method", "channel", "zone"]
    search_fields = ["number", "customer_name", "phone", "payment_reference"]
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]
    actions = ["mark_paid", "mark_shipped", "mark_delivered", "cancel_and_restock"]
    readonly_fields = [
        "number", "channel", "subtotal", "delivery_fee", "total", "created_at", "paid_at", "status",
    ]
    fieldsets = [
        (None, {"fields": ["number", "status", "channel", "created_at"]}),
        ("Customer", {"fields": ["customer_name", "phone", "zone", "address", "notes"]}),
        ("Payment", {"fields": ["payment_method", "payment_status", "payment_reference", "paid_at"]}),
        ("Money", {"fields": ["subtotal", "delivery_fee", "total"]}),
    ]

    # Orders come from the website or the stock list. Creating them here would
    # skip the stock count, so the add button is hidden for now.
    def has_add_permission(self, request):
        return False

    @admin.action(description="Payment received (Whish / OMT / cash)")
    def mark_paid(self, request, queryset):
        for order in queryset.exclude(status=Order.Status.CANCELLED):
            confirm_payment(order)
        self.message_user(request, "Marked as paid.", messages.SUCCESS)

    @admin.action(description="Out for delivery")
    def mark_shipped(self, request, queryset):
        n = queryset.exclude(status=Order.Status.CANCELLED).update(status=Order.Status.SHIPPED)
        self.message_user(request, f"{n} order(s) out for delivery.", messages.SUCCESS)

    @admin.action(description="Delivered")
    def mark_delivered(self, request, queryset):
        n = queryset.exclude(status=Order.Status.CANCELLED).update(status=Order.Status.DELIVERED)
        self.message_user(request, f"{n} order(s) delivered.", messages.SUCCESS)

    @admin.action(description="Cancel and put shoes back in stock")
    def cancel_and_restock(self, request, queryset):
        for order in queryset:
            cancel_order(order, user=request.user)
        self.message_user(request, "Cancelled. The pairs are back in stock.", messages.SUCCESS)
