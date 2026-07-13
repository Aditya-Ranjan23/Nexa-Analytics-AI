# Deployment Guide — Nexa Analytics v0.2.0 (Phase 1.5)

## Environments

| `DJANGO_ENV` | Purpose | Validation |
|--------------|---------|------------|
| `development` | Local dev (default) | Permissive — insecure defaults allowed |
| `staging` | Pre-production | Strict — same rules as production |
| `production` | Live deploy | Strict |

Startup validation runs from `config/env_validation.py` when settings load. Django will **refuse to start** in staging/production if any security constraint is violated.

---

## Development (default)

```bash
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

No `DJANGO_ENV` required (defaults to `development`).

---

## Production

### 1. Environment variables

```bash
DJANGO_ENV=production
DEBUG=False
DJANGO_SECRET_KEY=<50+ character random string>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
LOG_LEVEL=WARNING
MAX_UPLOAD_MB=25
```

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 2. Rate limit tuning (optional)

Override default throttle rates via environment:

```bash
THROTTLE_ANON_RATE=30/minute
THROTTLE_CHAT_ANON_RATE=10/minute
THROTTLE_UPLOAD_ANON_RATE=5/minute
```

See `.env.example` for all available knobs.

### 3. Settings module

```bash
export DJANGO_SETTINGS_MODULE=config.settings_production
```

`settings_production.py` sets `DJANGO_ENV=production` and `DEBUG=False` before loading base settings.

### 4. Deploy steps

```bash
python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application
```

### 5. Fail-fast behavior

If `DJANGO_ENV` is `production` or `staging` and any of these are true, **Django will not start**:

- `DEBUG=True`
- `DJANGO_SECRET_KEY` missing, too short, or a known placeholder
- `ALLOWED_HOSTS` is `*` or empty

---

## Health check

```bash
curl http://127.0.0.1:8000/health/
# {"status": "ok", "version": "0.2.0", "checks": {"database": "ok"}}
```

- Returns `200` when app and DB are healthy
- Returns `503` when the DB is unreachable (suitable for load-balancer / k8s readiness probes)

---

## CI/CD

GitHub Actions workflow at `.github/workflows/ci.yml` runs on every push/PR:

1. **Django system checks** — `manage.py check --fail-level WARNING`
2. **Migrations** — `manage.py migrate`
3. **Tests** — `manage.py test analytics_assistant`
4. **Lint** — `flake8` syntax/undefined-name gate
5. **Deploy check** — `manage.py check --deploy --settings=config.settings_production`

---

## Related docs

- [SECURITY.md](./SECURITY.md) — SSRF, upload, rate limiting, session security
- [ARCHITECTURE.md](./ARCHITECTURE.md) — system overview
- [TECHNICAL_DEBT.md](./TECHNICAL_DEBT.md) — known limitations and roadmap
