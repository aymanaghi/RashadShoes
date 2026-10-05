import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Create the panel login from environment variables if it doesn't exist yet.

    For hosts without a shell (e.g. Render free tier). Reads
    DJANGO_ADMIN_USERNAME and DJANGO_ADMIN_PASSWORD. Never changes an existing user.
    """

    help = "Create the shop panel admin from DJANGO_ADMIN_USERNAME / DJANGO_ADMIN_PASSWORD if missing."

    def handle(self, **options):
        username = os.environ.get("DJANGO_ADMIN_USERNAME", "").strip()
        password = os.environ.get("DJANGO_ADMIN_PASSWORD", "")
        if not username or not password:
            self.stdout.write("DJANGO_ADMIN_USERNAME / DJANGO_ADMIN_PASSWORD not set, skipping.")
            return
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Admin '{username}' already exists.")
            return
        User.objects.create_superuser(username=username, email="", password=password)
        self.stdout.write(self.style.SUCCESS(f"Created admin '{username}'."))
