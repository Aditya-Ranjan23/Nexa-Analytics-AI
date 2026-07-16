# Deployment Guide (v0.7.0)

This guide documents the procedures, environment controls, and verification steps required to deploy Nexa Analytics AI to production.

---

## 1. Environments & Context

Configuration behavior is governed by the `DJANGO_ENV` parameter variable:

| Environment | Mode | Access | Constraints Enforcement |
|---|---|---|---|
| **`development`** | Dev | Local | Permissive configuration, insecure secrets allowed (default) |
| **`staging`** | Test | Server | Strict security validation checks |
| **`production`** | Live | Public | Strict security validation checks, SSL required |

Target configuration checks run automatically on startup inside `config/env_validation.py`. The application will **throw an exception and refuse to boot** if any configuration gate is violated.

---

## 2. Environment Variables Specification

The following variables must be configured in production environments:

```bash
DJANGO_ENV=production
DEBUG=False
DJANGO_SECRET_KEY=<50+ character unique cryptographic secret string>
ALLOWED_HOSTS=analytics.nexa.example.com,nexa.example.com
NVIDIA_API_KEY=<NVIDIA API NIM authorization key>
LOG_LEVEL=WARNING
```

### Secret Key Generation
Generate a cryptographically safe production key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## 3. Production Deployment Commands

Execute the following setup commands inside the build environment:

```bash
# 1. Export settings target
export DJANGO_SETTINGS_MODULE=config.settings_production

# 2. Run system configuration checks
python manage.py check --deploy

# 3. Apply database schema migrations
python manage.py migrate

# 4. Consolidate static layout assets
python manage.py collectstatic --noinput

# 5. Launch application via WSGI runner
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

---

## 4. Application Health Check

Verify status endpoints for system liveness checks:

```bash
curl http://127.0.0.1:8000/health/
# {"status": "ok", "version": "0.7.0", "checks": {"database": "ok"}}
```
- Returns **`200 OK`** if the SQLite/PostgreSQL database connections resolve.
- Returns **`503 Service Unavailable`** if the database ping fails (ideal for load-balancer probes).

---

## 5. Continuous Integration (CI/CD)

The GitHub Actions build workflow (`.github/workflows/ci.yml`) executes the following checks on every pull request:
1. **Django System Check**: Runs `manage.py check --fail-level WARNING`.
2. **Migrations Check**: Verifies migration files compile cleanly.
3. **Automated Tests**: Runs `manage.py test` to ensure all 99 tests pass.
4. **Deploy Checks**: Executes `manage.py check --deploy --settings=config.settings_production`.
