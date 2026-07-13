# Nexa Analytics AI Assistant

**v0.2.0 Developer Preview** — Phase 1.5 Complete

AI-powered analytics dashboard backed by Django, NVIDIA AI, and a modular analytics engine.

## Features

- Full Django backend with analytics and AI chat APIs
- Modern dashboard frontend with KPI cards, trend chart, and assistant chat
- NVIDIA `build.nvidia.com` integration-ready service layer (falls back to local response)
- Role-aware dashboard (CEO, Marketing Manager, Team Member)
- Session-based chat memory persisted in DB
- Dataset upload (CSV/Excel) with auto schema detection and AI dashboard blueprint
- URL-ingested datasets with SSRF protection (DNS-aware + redirect-chain validation)
- Pluggable analytics datasource layer (CSV, PostgreSQL)
- API rate limiting on all resource-intensive endpoints (configurable)
- Anonymous session isolation via browser session key binding

## Security Posture (Phase 1.5)

- SSRF: DNS-aware URL validation + redirect-chain re-validation
- Upload: file size limit (25 MB default), MIME type check
- Sessions: anonymous sessions bound to Django session key
- Production: fail-fast on insecure SECRET_KEY, DEBUG=True, or wildcard ALLOWED_HOSTS
- Rate limiting: DRF throttle classes on chat, upload, and ingestion endpoints

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Set NVIDIA_API_KEY from build.nvidia.com (optional)

# 3. Run migrations
python manage.py migrate

# 4. Start server
python manage.py runserver

# 5. Open
# http://127.0.0.1:8000/
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/analytics/summary/` | KPIs, trends, channel performance (`?role=ceo\|marketing_manager\|team_member`) |
| `GET` | `/api/dashboard/role/` | Role-scoped widgets and KPI payload |
| `POST` | `/api/chat/` | AI chat — body: `{"message": "...", "role": "...", "session_id": 12}` |
| `POST` | `/api/data/upload/` | Multipart CSV/Excel upload with auto schema detection |
| `POST` | `/api/data/upload-link/` | JSON `{"url": "https://..."}` to ingest remote dataset |
| `POST` | `/api/ingestion/run/` | Manual ingestion job trigger |
| `GET/POST` | `/api/dashboard/blueprint/` | Load/save dashboard blueprint override |
| `GET` | `/health/` | Liveness + DB readiness check (503 on DB failure) |

## Configuration

See [`.env.example`](.env.example) for all available settings.

Key environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_ENV` | `development` | `development` / `staging` / `production` |
| `DJANGO_SECRET_KEY` | dev-only placeholder | **Required in production** |
| `NVIDIA_API_KEY` | _(empty)_ | Optional — AI falls back without it |
| `MAX_UPLOAD_MB` | `25` | Upload size limit in MB |
| `THROTTLE_CHAT_ANON_RATE` | `20/minute` | Chat rate limit for anonymous users |

## Project Structure

```
config/              Django project config (settings, URLs, env validation)
analytics_assistant/ Backend app (views, analytics engines, services, tests)
  ├── analytics.py   Analytics facade
  ├── chart_engine.py Chart data builder
  ├── kpi_engine.py  KPI computation
  ├── insights_engine.py Insight generation
  ├── upload_service.py File/URL dataset ingestion
  ├── url_safety.py  SSRF guard with DNS + redirect validation
  ├── throttles.py   DRF scoped rate limit classes
  ├── services.py    NVIDIA AI service layer
  ├── models.py      ChatSession, DatasetUpload, DashboardState, IngestionJob
  └── tests.py       57 automated tests
templates/           Dashboard HTML
static/              CSS + JS
data/sales_data.csv  Seed dataset (HR analytics, zero-config fallback)
docs/                Architecture, security, deployment, debt register, changelog
.github/workflows/   CI/CD (GitHub Actions)
```

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture and ADRs |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment guide |
| [SECURITY.md](docs/SECURITY.md) | Security model and checklist |
| [TECHNICAL_DEBT.md](docs/TECHNICAL_DEBT.md) | Known limitations and Phase 2 roadmap |
| [CHANGELOG.md](docs/CHANGELOG.md) | Version history |

## Roles

- `ceo` — revenue, ROAS, top-line KPIs
- `marketing_manager` — campaign actions, channel breakdown
- `team_member` — general analytics

Roles resolved from authenticated user groups (logged in) or `?role=` query param.

## Dataset Modes

- **Ads mode** — requires `date, channel, revenue, orders, ad_spend, conversion_rate`
- **Generic mode** — accepts any dataset with 2+ columns

## Running Tests

```bash
python manage.py test analytics_assistant --verbosity=2
# 57 tests, ~3 seconds
```
