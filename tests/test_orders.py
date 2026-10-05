from decimal import Decimal

import pytest

from catalog.stock import NotEnoughStock
from orders.models import Order
from orders.services import Line, cancel_order, confirm_payment, place_order


def test_order_takes_pairs_and_totals_with_delivery(make_product, zone):
    product = make_product(price="85", stock={"42": 2, "43": 1})
    v42 = product.variants.get(size="42")
    v43 = product.variants.get(size="43")

    order = place_order(
        [Line(v42, 2), Line(v43, 1)], customer_name="Ali", phone="03123456", zone=zone
    )

    v42.refresh_from_db(); v43.refresh_from_db()
    assert (v42.stock, v43.stock) == (0, 0)
    assert order.subtotal == Decimal("255")
    assert order.delivery_fee == Decimal("3")
    assert order.total == Decimal("258")
    assert order.number.startswith("R")
    assert order.movements.filter(reason="sale").count() == 2


def test_failed_order_saves_nothing(make_product):
    product = make_product(stock={"42": 2, "43": 0})
    v42, v43 = product.variants.get(size="42"), product.variants.get(size="43")

    with pytest.raises(NotEnoughStock):
        place_order([Line(v42, 1), Line(v43, 1)], customer_name="Ali", phone="03")

    v42.refresh_from_db()
    assert v42.stock == 2
    assert Order.objects.count() == 0


def test_whish_with_reference_waits_for_owner_check(make_product):
    v = make_product().variants.get()
    order = place_order(
        [Line(v)], customer_name="Rana", phone="70", payment_method="whish", payment_reference="WH-889"
    )
    assert order.payment_status == Order.PaymentStatus.AWAITING

    confirm_payment(order)
    order.refresh_from_db()
    assert order.payment_status == Order.PaymentStatus.PAID
    assert order.status == Order.Status.CONFIRMED
    assert order.paid_at is not None


def test_cancel_puts_pairs_back_once(make_product):
    v = make_product(stock={"42": 3}).variants.get()
    order = place_order([Line(v, 2)], customer_name="Ali", phone="03")

    cancel_order(order)
    cancel_order(order)  # second click does nothing

    v.refresh_from_db()
    assert v.stock == 3
    assert Order.objects.get().status == Order.Status.CANCELLED


def test_order_numbers_are_unique_per_day(make_product):
    v = make_product(stock={"42": 5}).variants.get()
    a = place_order([Line(v)], customer_name="A", phone="1")
    b = place_order([Line(v)], customer_name="B", phone="2")
    assert a.number != b.number
    assert b.number.endswith("-002")
