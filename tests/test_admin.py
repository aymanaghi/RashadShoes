import pytest
from django.urls import reverse

from catalog.models import Brand, Product, StockMovement, Variant


@pytest.fixture
def owner(admin_client):
    return admin_client


def _product_form(product=None, brand=None, **overrides):
    data = {
        "brand": (product.brand_id if product else brand.pk),
        "name": product.name if product else "Samba OG",
        "category": "",
        "gender": "unisex",
        "price": "90",
        "compare_at_price": "",
        "description": "",
        "is_active": "on",
        "quick_color": "",
        "quick_sizes": "",
        "quick_qty": "1",
        "variants-TOTAL_FORMS": "0",
        "variants-INITIAL_FORMS": "0",
        "images-TOTAL_FORMS": "0",
        "images-INITIAL_FORMS": "0",
    }
    data.update(overrides)
    return data


def test_quick_add_sizes_creates_rows_with_stock(owner, db):
    brand = Brand.objects.create(name="Adidas")
    response = owner.post(
        reverse("admin:catalog_product_add"),
        _product_form(brand=brand, quick_color="white", quick_sizes="40-42", quick_qty="2"),
    )
    assert response.status_code == 302, response.content[:2000]
    product = Product.objects.get(name="Samba OG")
    assert sorted(product.variants.values_list("size", "stock")) == [("40", 2), ("41", 2), ("42", 2)]
    assert StockMovement.objects.filter(reason="initial").count() == 3


def test_editing_stock_in_panel_is_logged(owner, make_product):
    product = make_product(stock={"42": 2})
    v = product.variants.get()
    data = _product_form(product, **{
        "variants-TOTAL_FORMS": "1",
        "variants-INITIAL_FORMS": "1",
        "variants-0-id": str(v.pk),
        "variants-0-product": str(product.pk),
        "variants-0-color": "White",
        "variants-0-size": "42",
        "variants-0-stock": "5",
        "variants-0-price_override": "",
    })

    response = owner.post(reverse("admin:catalog_product_change", args=[product.pk]), data)

    assert response.status_code == 302
    v.refresh_from_db()
    assert v.stock == 5
    assert v.movements.filter(reason="adjustment", change=3).exists()


def test_sold_one_action(owner, make_product):
    v = make_product(stock={"42": 1}).variants.get()
    url = reverse("admin:catalog_variant_changelist")
    owner.post(url, {"action": "sold_one", "_selected_action": [v.pk]})
    owner.post(url, {"action": "sold_one", "_selected_action": [v.pk]})  # already out
    v.refresh_from_db()
    assert v.stock == 0
    assert v.movements.filter(reason="sale").count() == 1


@pytest.mark.parametrize("name", ["catalog_product", "catalog_variant", "catalog_stockmovement", "orders_order", "orders_deliveryzone"])
def test_panel_pages_load(owner, make_product, name):
    make_product()
    assert owner.get(reverse(f"admin:{name}_changelist")).status_code == 200
