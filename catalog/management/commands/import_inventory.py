from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog.importer import import_inventory


class Command(BaseCommand):
    help = "Import shoes and stock counts from a CSV file (see sample_data/inventory_template.csv)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--dry-run", action="store_true", help="Check the file and show what would change, save nothing.")

    def handle(self, csv_path, dry_run, **options):
        path = Path(csv_path)
        if not path.exists():
            raise CommandError(f"No file at {path}")
        report = import_inventory(path.read_text(encoding="utf-8-sig"), dry_run=dry_run)
        if report.errors:
            for err in report.errors:
                self.stderr.write(self.style.ERROR(err))
            raise CommandError(f"{len(report.errors)} problem(s) in the file. Nothing was imported.")
        prefix = "Dry run, nothing saved: " if dry_run else "Imported: "
        self.stdout.write(self.style.SUCCESS(prefix + report.summary()))
