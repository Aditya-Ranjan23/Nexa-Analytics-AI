"""
Production Django settings.

Usage:
  DJANGO_SETTINGS_MODULE=config.settings_production

Set DJANGO_SECRET_KEY and ALLOWED_HOSTS in the environment before starting.
"""

import os

os.environ.setdefault("DJANGO_ENV", "production")
os.environ.setdefault("DEBUG", "False")

from .settings import *  # noqa: E402, F403
