import pytest

from catalog.models import StockMovement, Variant
from catalog.stock import NotEnoughStock, adjust_stock, set_stock
from catalog.utils import format_money, parse_sizes


def test_adjust_stock_logs_every_change(make_product):
    variant = make_product(stock={"42": 2}).variants.get()

    adjust_stock(variant, 3, StockMovement.Reason.RESTOCK)
    adjust_stock(variant, -1, StockMovement.Reason.SALE)

    variant.refresh_from_db()
    assert variant.stock == 4
    log = list(variant.movements.order_by("id").values_list("change", "stock_after", "reason"))
    assert log == [(2, 2, "initial"), (3, 5, "restock"), (-1, 4, "sale")]


def test_cannot_sell_more_than_on_shelf(make_product):
    variant = make_product(stock={"42": 1}).variants.get()

    with pytest.raises(NotEnoughStock):
        adjust_stock(variant, -2, StockMovement.Reason.SALE)

    variant.refresh_from_db()
    assert variant.stock == 1
    assert variant.movements.count() == 1  # only the first count


def test_set_stock_logs_the_difference(make_product):
    variant = make_product(stock={"42": 5}).variants.get()

    movement = set_stock(variant, 3, StockMovement.Reason.ADJUSTMENT)

    assert movement.change == -2
    assert set_stock(variant, 3, StockMovement.Reason.ADJUSTMENT) is None


def test_variant_gets_short_code_and_tidy_fields(make_product):
    product = make_product(stock={})
    v = Variant.objects.create(product=product, color="  black ", size="42,5")
    assert v.sku == f"RS-{v.pk:05d}"
    assert v.color == "Black"
    assert v.size == "42.5"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("40-44", ["40", "41", "42", "43", "44"]),
        ("36.5-38", ["36.5", "37", "37.5", "38"]),
        ("40, 41, 43", ["40", "41", "43"]),
        ("39 40 40", ["39", "40"]),
        ("40–42", ["40", "41", "42"]),
        ("", []),
    ],
)
def test_parse_sizes(text, expected):
    assert parse_sizes(text) == expected


@pytest.mark.parametrize("bad", ["44-40", "a-b", "20-60"])
def test_parse_sizes_rejects_nonsense(bad):
    with pytest.raises(ValueError):
        parse_sizes(bad)


def test_format_money():
    assert format_money("85.00") == "85"
    assert format_money("85.5") == "85.50"
    assert format_money("1250") == "1,250"
