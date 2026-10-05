from urllib.parse import quote

from django.conf import settings

from .utils import format_money


def shop_number() -> str:
    return "".join(ch for ch in settings.SHOP["WHATSAPP"] if ch.isdigit())


def order_message(product, variant=None, page_url: str = "") -> str:
    shop = settings.SHOP
    symbol = shop["CURRENCY_SYMBOL"]
    if variant is not None:
        lines = [
            f"Hello {shop['NAME']}, I'd like to order:",
            f"{product}",
            f"Colour: {variant.color}",
            f"Size: {variant.size}",
            f"Price: {symbol}{format_money(variant.price)}",
            f"Code: {variant.sku}",
        ]
    else:
        lines = [
            f"Hello {shop['NAME']}, I'm interested in:",
            f"{product}",
            "Which sizes do you have?",
        ]
    if page_url:
        lines.append(page_url)
    return "\n".join(lines)


def order_link(product, variant=None, page_url: str = "") -> str | None:
    """wa.me link with the message already typed. None if no shop number is set."""
    number = shop_number()
    if not number:
        return None
    return f"https://wa.me/{number}?text={quote(order_message(product, variant, page_url))}"
