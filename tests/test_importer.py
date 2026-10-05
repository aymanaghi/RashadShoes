from decimal import Decimal

from django.core.management import call_command

from catalog.importer import import_inventory
from catalog.models import Product, Variant

CSV = """brand,model,category,gender,color,sizes,pairs,price,compare_at_price
Nike,Air Force 1,Sneakers,men,White,40-42,2,85,
Nike,Air Force 1,Sneakers,men,Black,41,1,85,
Skechers,Go Walk 6,Comfort,women,Navy,36-37,3,65,75
"""


def test_import_creates_products_sizes_and_stock(db):
    report = import_inventory(CSV)

    assert report.errors == []
    assert report.products_created == 2
    assert report.products_updated == 0
    assert report.variants_created == 6
    assert report.pairs_total == 13
    af1 = Product.objects.get(name="Air Force 1")
    assert sorted(af1.variants.values_list("color", "size", "stock")) == [
        ("Black", "41", 1), ("White", "40", 2), ("White", "41", 2), ("White", "42", 2),
    ]
    assert Product.objects.get(name="Go Walk 6").on_sale


def test_reimport_updates_counts_and_prices_without_duplicates(db):
    import_inventory(CSV)
    changed = CSV.replace("White,40-42,2,85", "White,40-42,5,79")

    report = import_inventory(changed)

    assert report.products_created == 0
    assert report.products_updated == 2
    assert report.variants_changed == 3
    assert Variant.objects.count() == 6
    af1 = Product.objects.get(name="Air Force 1")
    assert af1.price == Decimal("79")
    v = af1.variants.get(color="White", size="40")
    assert v.stock == 5
    assert v.movements.filter(reason="adjustment", change=3).exists()
    # Black stayed at 85 in the file, so only that colour keeps the old price.
    black = af1.variants.get(color="Black")
    assert black.price == Decimal("85")
    assert v.price == Decimal("79")


def test_dry_run_saves_nothing(db):
    report = import_inventory(CSV, dry_run=True)
    assert report.products_created == 2
    assert Product.objects.count() == 0


def test_file_with_mistakes_is_rejected_whole(db):
    bad = CSV + "Adidas,Samba,Sneakers,aliens,White,40,1,90,\nAdidas,Gazelle,,men,Blue,40,x,90,\n"
    report = import_inventory(bad)
    assert len(report.errors) == 2
    assert "gender" in report.errors[0]
    assert "pairs" in report.errors[1]
    assert Product.objects.count() == 0


def test_missing_columns_reported(db):
    report = import_inventory("brand,model\nNike,AF1\n")
    assert report.errors and "Missing columns" in report.errors[0]


def test_seed_demo_command_loads_template(db):
    call_command("seed_demo")
    assert Product.objects.count() == 5  # Air Force 1 has two colour rows
    from orders.models import DeliveryZone
    assert DeliveryZone.objects.filter(name="Tripoli").exists()
