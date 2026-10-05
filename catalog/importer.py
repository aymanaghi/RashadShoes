"""Load the shop's inventory from a CSV (the digitised notebook).

One row = one shoe model in one colour. Sizes can be a range, so a notebook
line like "Nike Air Force 1, white, 40 to 44, 2 of each, $85" becomes one row:

    brand,model,category,gender,color,sizes,pairs,price
    Nike,Air Force 1,Sneakers,men,White,40-44,2,85

Optional columns: compare_at_price, description, sku (only for single-size rows).
Running the same file again updates prices and sets stock to the file's counts,
logging the difference. It never deletes anything.
"""

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .models import Brand, Category, Gender, Product, StockMovement, Variant
from .stock import adjust_stock, set_stock
from .utils import parse_sizes

REQUIRED = {"brand", "model", "color", "sizes", "pairs", "price"}
GENDER_WORDS = {
    "men": Gender.MEN, "man": Gender.MEN, "male": Gender.MEN, "m": Gender.MEN, "رجالي": Gender.MEN,
    "women": Gender.WOMEN, "woman": Gender.WOMEN, "female": Gender.WOMEN, "w": Gender.WOMEN, "نسائي": Gender.WOMEN,
    "kids": Gender.KIDS, "kid": Gender.KIDS, "children": Gender.KIDS, "k": Gender.KIDS, "ولادي": Gender.KIDS,
    "unisex": Gender.UNISEX, "": Gender.UNISEX,
}


@dataclass
class ImportReport:
    products_created: int = 0
    products_updated: int = 0
    variants_created: int = 0
    variants_changed: int = 0
    pairs_total: int = 0
    errors: list[str] = field(default_factory=list)
    seen_products: set[int] = field(default_factory=set, repr=False)

    def summary(self) -> str:
        return (
            f"{self.products_created} new shoe models, {self.products_updated} updated; "
            f"{self.variants_created} new sizes, {self.variants_changed} stock counts changed; "
            f"{self.pairs_total} pairs in the file"
        )


class _DryRun(Exception):
    pass


def _money(value: str, row_no: int, column: str) -> Decimal | None:
    value = (value or "").replace("$", "").replace(",", "").strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError(f"row {row_no}: '{value}' in {column} is not a price")


def import_inventory(text: str, *, dry_run: bool = False, user=None) -> ImportReport:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    headers = {h.strip().lower() for h in (reader.fieldnames or [])}
    missing = REQUIRED - headers
    report = ImportReport()
    if missing:
        report.errors.append("Missing columns: " + ", ".join(sorted(missing)))
        return report

    rows = []
    for row_no, raw in enumerate(reader, start=2):  # row 1 is the header
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        if not any(row.values()):
            continue
        try:
            rows.append((row_no, _parse_row(row, row_no)))
        except ValueError as exc:
            report.errors.append(str(exc))

    if report.errors:
        return report  # don't half-import a file with mistakes

    try:
        with transaction.atomic():
            for _, parsed in rows:
                _apply(parsed, report, user)
            if dry_run:
                raise _DryRun
    except _DryRun:
        pass
    return report


def _parse_row(row: dict, row_no: int) -> dict:
    for col in ("brand", "model", "color", "sizes"):
        if not row.get(col):
            raise ValueError(f"row {row_no}: {col} is empty")
    gender_word = row.get("gender", "").lower()
    if gender_word not in GENDER_WORDS:
        raise ValueError(f"row {row_no}: gender '{row['gender']}' should be men, women, kids or unisex")
    try:
        sizes = parse_sizes(row["sizes"])
    except ValueError as exc:
        raise ValueError(f"row {row_no}: {exc}")
    try:
        pairs = int(row["pairs"] or 0)
        if pairs < 0:
            raise ValueError
    except ValueError:
        raise ValueError(f"row {row_no}: pairs '{row['pairs']}' should be a whole number")
    price = _money(row["price"], row_no, "price")
    if price is None:
        raise ValueError(f"row {row_no}: price is empty")
    sku = row.get("sku", "")
    if sku and len(sizes) > 1:
        raise ValueError(f"row {row_no}: a code (sku) only works on a row with one size")
    return {
        "brand": row["brand"],
        "model": row["model"],
        "category": row.get("category", ""),
        "gender": GENDER_WORDS[gender_word],
        "color": row["color"],
        "sizes": sizes,
        "pairs": pairs,
        "price": price,
        "compare_at_price": _money(row.get("compare_at_price", ""), row_no, "compare_at_price"),
        "description": row.get("description", ""),
        "sku": sku,
    }


def _apply(p: dict, report: ImportReport, user) -> None:
    brand = Brand.objects.filter(name__iexact=p["brand"]).first() or Brand.objects.create(name=p["brand"])
    category = None
    if p["category"]:
        category = (
            Category.objects.filter(name__iexact=p["category"]).first()
            or Category.objects.create(name=p["category"].title())
        )

    product = Product.objects.filter(brand=brand, name__iexact=p["model"]).first()
    if product is None:
        product = Product(brand=brand, name=p["model"])
        report.products_created += 1
    elif product.pk not in report.seen_products:
        report.products_updated += 1

    # The first row of a shoe in this file sets its price. A later row (another
    # colour) with a different price gets that price on its own sizes only.
    first_row_for_product = product.pk is None or product.pk not in report.seen_products
    if first_row_for_product:
        product.category = category or product.category
        product.gender = p["gender"]
        product.price = p["price"]
        if p["compare_at_price"] is not None:
            product.compare_at_price = p["compare_at_price"]
        if p["description"]:
            product.description = p["description"]
        product.save()
        report.seen_products.add(product.pk)
    price_override = None if p["price"] == product.price else p["price"]

    color = p["color"].strip().title()
    for size in p["sizes"]:
        variant, created = Variant.objects.get_or_create(
            product=product, color=color, size=size,
            defaults={"sku": p["sku"] or None, "price_override": price_override},
        )
        if not created and variant.price_override != price_override:
            variant.price_override = price_override
            variant.save(update_fields=["price_override"])
        report.pairs_total += p["pairs"]
        if created:
            report.variants_created += 1
            adjust_stock(variant, p["pairs"], StockMovement.Reason.INITIAL, note="Imported", user=user)
        elif variant.stock != p["pairs"]:
            report.variants_changed += 1
            set_stock(variant, p["pairs"], StockMovement.Reason.ADJUSTMENT, note="Re-imported count", user=user)
