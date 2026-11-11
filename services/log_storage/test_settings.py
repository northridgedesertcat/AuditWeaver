"""Isolated SQLite settings for API and metadata regression tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "website/backend/v1"))
from backend.settings import *  # noqa: F403

SECRET_KEY = "isolated-log-storage-tests-only-with-a-long-signing-key"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
