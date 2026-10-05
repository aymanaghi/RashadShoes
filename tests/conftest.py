from decimal import Decimal

import pytest

from catalog.models import Brand, Category, Gender, Product, StockMovement, Variant
from catalog.stock import adjust_stock
from orders.models import DeliveryZone


@pytest.fixture
def make_product(db):
    def _make(name="Air Force 1", brand="Nike", category="Sneakers", gender=Gender.MEN,
              price="85", stock=None, color="White", **extra):
        b, _ = Brand.objects.get_or_create(name=brand)
        c, _ = Category.objects.get_or_create(name=category)
        product = Product.objects.create(
            name=name, brand=b, category=c, gender=gender, price=Decimal(price), **extra
        )
        for size, pairs in (stock or {"42": 2}).items():
            v = Variant.objects.create(product=product, color=color, size=size)
            adjust_stock(v, pairs, StockMovement.Reason.INITIAL)
        return product

    return _make


@pytest.fixture
def zone(db):
    return DeliveryZone.objects.create(name="Tripoli", fee=Decimal("3"))


@pytest.fixture
def whatsapp(settings):
    settings.SHOP = {**settings.SHOP, "WHATSAPP": "+961 3 123 456"}
    return "9613123456"
