"""Deployment environment validation (fail-fast on insecure production config)."""

from django.core.exceptions import ImproperlyConfigured

# Must match the dev fallback in settings.py — used only for comparison, not as a live secret.
INSECURE_DEV_SECRET_KEY = (
    "django-insecure-on$ras0o5e_l6+_qo4f9%)-cqrteb(7i6fwgj$mlyfvdmrkk!k"
)

VALID_ENVS = frozenset({"development", "staging", "production"})
MIN_SECRET_KEY_LENGTH = 50


def is_insecure_secret_key(secret_key: str) -> bool:
    if not secret_key:
        return True
    if secret_key == INSECURE_DEV_SECRET_KEY:
        return True
    if secret_key.strip().lower() in {"change-me", "change-me-in-production", "secret", "changeme"}:
        return True
    return len(secret_key) < MIN_SECRET_KEY_LENGTH


def validate_deployment_env(
    *,
    django_env: str,
    debug: bool,
    secret_key: str,
    allowed_hosts: list[str],
) -> None:
    env = (django_env or "development").strip().lower()
    if env not in VALID_ENVS:
        raise ImproperlyConfigured(
            f"DJANGO_ENV must be one of {sorted(VALID_ENVS)}; got '{django_env}'."
        )

    if env == "development":
        return

    errors: list[str] = []

    if debug:
        errors.append("DEBUG must be False when DJANGO_ENV is staging or production.")

    if is_insecure_secret_key(secret_key):
        errors.append(
            "DJANGO_SECRET_KEY must be set to a unique random value "
            f"({MIN_SECRET_KEY_LENGTH}+ characters) when DJANGO_ENV is {env}."
        )

    normalized_hosts = [host.strip() for host in allowed_hosts if host.strip()]
    if not normalized_hosts or normalized_hosts == ["*"]:
        errors.append(
            f"ALLOWED_HOSTS must list explicit hostnames when DJANGO_ENV is {env} (not '*')."
        )

    if errors:
        raise ImproperlyConfigured(
            "Insecure deployment configuration detected:\n- " + "\n- ".join(errors)
        )
