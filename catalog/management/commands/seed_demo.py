from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand

from catalog.importer import import_inventory
from orders.models import DeliveryZone

# Example areas and fees. Edit the real ones in the panel under Delivery zones.
EXAMPLE_ZONES = [
    ("Tripoli", "3"),
    ("North Lebanon", "4"),
    ("Beirut", "5"),
    ("Mount Lebanon", "5"),
    ("Bekaa", "6"),
    ("South Lebanon", "6"),
]


class Command(BaseCommand):
    help = "Load example shoes and delivery areas so the site has something to show while developing."

    def handle(self, **options):
        path = settings.BASE_DIR / "sample_data" / "inventory_template.csv"
        report = import_inventory(path.read_text(encoding="utf-8-sig"))
        if report.errors:
            for err in report.errors:
                self.stderr.write(err)
            return
        for position, (name, fee) in enumerate(EXAMPLE_ZONES):
            DeliveryZone.objects.get_or_create(name=name, defaults={"fee": Decimal(fee), "position": position})
        self.stdout.write(self.style.SUCCESS("Example data loaded: " + report.summary()))
