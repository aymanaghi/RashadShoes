from decimal import Decimal, InvalidOperation


def parse_sizes(text: str) -> list[str]:
    """Turn what the owner types into a list of sizes.

    "40-44"        -> ["40", "41", "42", "43", "44"]
    "36.5-38"      -> ["36.5", "37", "37.5", "38"]   (half sizes if the start is a half)
    "40, 41, 43"   -> ["40", "41", "43"]
    "39 40 41"     -> ["39", "40", "41"]
    """
    text = (text or "").replace("–", "-").replace("—", "-").strip()
    if not text:
        return []
    sizes: list[str] = []
    for chunk in text.replace(",", " ").split():
        if "-" in chunk and not chunk.startswith("-"):
            start_s, end_s = chunk.split("-", 1)
            try:
                start, end = Decimal(start_s), Decimal(end_s)
            except InvalidOperation:
                raise ValueError(f"Can't read size range '{chunk}'")
            if end < start or end - start > 20:
                raise ValueError(f"Size range '{chunk}' looks wrong")
            step = Decimal("0.5") if start % 1 else Decimal("1")
            value = start
            while value <= end:
                sizes.append(format_size(value))
                value += step
        else:
            sizes.append(format_size_text(chunk))
    # keep order, drop duplicates
    return list(dict.fromkeys(sizes))


def format_money(value) -> str:
    """85.00 -> '85', 85.50 -> '85.50', 1250 -> '1,250'."""
    value = Decimal(value)
    if value == value.to_integral():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def format_size(value: Decimal) -> str:
    return str(int(value)) if value == value.to_integral() else str(value.normalize())


def format_size_text(text: str) -> str:
    text = text.strip().replace(",", ".")
    try:
        return format_size(Decimal(text))
    except InvalidOperation:
        return text.upper()
