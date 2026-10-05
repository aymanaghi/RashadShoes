from django.contrib.auth import get_user_model
from django.core.management import call_command


def test_ensure_admin_creates_once(db, monkeypatch):
    monkeypatch.setenv("DJANGO_ADMIN_USERNAME", "rashad")
    monkeypatch.setenv("DJANGO_ADMIN_PASSWORD", "first-pass-123")
    call_command("ensure_admin")
    monkeypatch.setenv("DJANGO_ADMIN_PASSWORD", "changed")
    call_command("ensure_admin")  # restart must not reset the password

    user = get_user_model().objects.get(username="rashad")
    assert user.is_superuser
    assert user.check_password("first-pass-123")


def test_ensure_admin_skips_without_settings(db, monkeypatch):
    monkeypatch.delenv("DJANGO_ADMIN_USERNAME", raising=False)
    call_command("ensure_admin")
    assert not get_user_model().objects.exists()
