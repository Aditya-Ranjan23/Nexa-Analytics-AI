# Nexa Analytics AI Assistant — Architecture (Phase 1 RC)

**Version:** Phase 1 Release Candidate  
**Stack:** Django 6 · DRF · Pandas · SQLite · Chart.js · NVIDIA API  
**Last updated:** 2026-07-13

---

## 1. System Purpose

Nexa Analytics is an AI-powered Business Intelligence dashboard. Users upload tabular datasets (CSV/Excel), view auto-generated KPIs and charts, receive rule-based and AI-generated insights, and chat with an assistant grounded in live analytics data.

Phase 1 focused on **stabilization**: no new product features; hardening architecture, security, testing, and maintainability.

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Client (Browser)                          │
│  dashboard.html · dashboard.css · dashboard.js · Chart.js        │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTP (JSON + multipart)
┌────────────────────────────▼─────────────────────────────────────┐
│                     Django + DRF (config/)                       │
│  Middleware: Security, Session, CSRF, Auth                        │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│                   analytics_assistant (app)                      │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │ views.py    │  │ serializers  │  │ request_context.py      │ │
│  │ (thin HTTP) │  │ (validation) │  │ (dashboard state)       │ │
│  └──────┬──────┘  └──────────────┘  └─────────────────────────┘ │
│         │                                                        │
│  ┌──────┴──────┬──────────────┬──────────────┬─────────────────┐ │
│  │ chat_       │ upload_      │ analytics.py │ services.py    │ │
│  │ service     │ service      │ (facade)     │ (NVIDIA AI)      │ │
│  └──────┬──────┴──────┬───────┴──────┬───────┴─────────────────┘ │
│         │             │              │                           │
│         │             │    ┌─────────┴─────────┐                 │
│         │             │    │ Analytics Engines│                 │
│         │             │    │ kpi · chart ·    │                 │
│         │             │    │ insights · column│                 │
│         │             │    └─────────┬─────────┘                 │
│         │             │              │                           │
│         └─────────────┴──────────────┼───────────────────────────┘
│                                      ▼
│                         dataset_pipeline.py
│                         (single data resolution path)
└────────────────────────────┬─────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   media/datasets/     PostgreSQL (opt)    data/sales_data.csv
   DatasetUpload        ANALYTICS_SOURCE     read-only seed
         │
         ▼
   SQLite (db.sqlite3)
   ChatSession · ChatMessage · DashboardState · IngestionJob
```

---

## 3. Module Reference

### 3.1 HTTP Layer

| Module | Lines (approx) | Responsibility |
|--------|----------------|----------------|
| `views.py` | 199 | Thin REST controllers; delegates to services |
| `serializers.py` | 24 | DRF input validation (chat, upload-link, blueprint, ingestion) |
| `request_context.py` | 34 | `resolve_dashboard_state`, session ownership |
| `urls.py` | 25 | Route table (9 endpoints + dashboard UI) |

### 3.2 Service Layer

| Module | Responsibility |
|--------|----------------|
| `chat_service.py` | Chat session resolution, memory context, NVIDIA orchestration |
| `upload_service.py` | File/URL ingestion, schema validation, dataset activation |
| `services.py` | NVIDIA API client, blueprint generation, dataset brief, fallback chat |
| `url_safety.py` | SSRF mitigation for URL ingestion |

### 3.3 Analytics Layer

| Module | Responsibility |
|--------|----------------|
| `analytics.py` | Public facade: `build_analytics_payload`, mode routing (ads vs generic) |
| `kpi_engine.py` | KPI card construction, format inference, clamping |
| `chart_engine.py` | Line/bar/doughnut specs, time series, chart fallbacks |
| `insights_engine.py` | Rule-based insight cards (ads + generic) |
| `column_utils.py` | ID-column filtering, metric ranking, date/dimension detection |

### 3.4 Data Layer

| Module | Responsibility |
|--------|----------------|
| `dataset_pipeline.py` | **Single load path** — upload → postgres → seed CSV |
| `data_loaders.py` | CSV/Excel parsing, multi-sheet merge logic |
| `data_sources.py` | PostgreSQL + seed CSV connectors |
| `dataset_profile.py` | Column profiling for AI blueprint generation |
| `schema.py` | Dataset column validation (ads vs generic mode) |

### 3.5 Domain

| Module | Responsibility |
|--------|----------------|
| `models.py` | ChatSession, ChatMessage, DatasetUpload, DatasetVersion, DashboardState, IngestionJob |
| `admin.py` | Django admin for all models |

### 3.6 Frontend

| Asset | Responsibility |
|-------|----------------|
| `templates/.../dashboard.html` | 4-tab SPA shell (Dashboard, Upload, Insights, Ask AI) |
| `static/js/dashboard.js` | API client, Chart.js rendering, chat UI |
| `static/css/dashboard.css` | Dashboard styling |

---

## 4. Dataset Pipeline (ADR-016)

All analytics reads flow through `dataset_pipeline.load_active_dataframe()`:

```
resolve_active_upload(dataset_upload)
        │
        ├─► DatasetUpload.stored_path exists? ──► load_dataframe_from_path()
        │
        ├─► ANALYTICS_SOURCE == postgres? ──────► PostgresDataSource.load()
        │
        └─► else ───────────────────────────────► load_seed_dataset()
                                                    (data/sales_data.csv)
```

**Blueprint resolution** uses the same upload record via `active_blueprint()`.

**Upload writes** go only to `media/datasets/` via `DatasetUpload.stored_path`. The seed CSV is **never modified** on upload (Phase 1 change — eliminates dual-path drift).

---

## 4.1 Dataset Versioning & History

Chronological version control is built directly on the multi-dataset foundation:

- **Database Snapshotting**: The `DatasetVersion` model captures complete file metadata, row counts, and blueprints. Each version belongs to a parent `DatasetUpload` through a ForeignKey, indexed by `version_number`.
- **Upload Incrementation**: When a new version file or URL is submitted for an existing dataset, the parent record is updated with the new row count, path, and blueprint, and `active_version_number` is bumped. A new `DatasetVersion` record is saved.
- **Comparison Engine**: Version comparison evaluates structural schemas (added/removed columns) and statistical profiles (mean, min, max, diffs) for common numeric columns.
- **Rollback System**: Restoring a version overwrites the parent `DatasetUpload` path, file, row count, and active blueprint to match the target `DatasetVersion` record, updating the dashboard state instantly.

---

## 5. Analytics Modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| **ads** | All columns present: `date`, `channel`, `revenue`, `orders`, `ad_spend`, `conversion_rate` | Ad-specific KPIs, channel charts, Meta Ads signals |
| **generic** | Any dataset with ≥2 columns | Auto-detects numeric/categorical columns, builds KPIs/charts from blueprint hints |

Mode detection: `schema.validate_dataset_columns()` + column subset check in `analytics.py`.

---

## 6. API Surface

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Dashboard UI |
| GET | `/api/analytics/summary/` | Full analytics payload |
| POST | `/api/chat/` | AI chat with session memory |
| GET/POST | `/api/dashboard/blueprint/` | Load/save blueprint override |
| POST | `/api/data/upload/` | File upload (CSV/Excel) |
| POST | `/api/data/upload-link/` | URL ingestion (SSRF-guarded) |
| POST | `/api/ingestion/run/` | Manual ingestion job log |
| GET | `/health/` | Health check |

---

## 7. Data Model

```
User (Django auth, optional)
  ├── ChatSession (role, title)
  │     └── ChatMessage (user/assistant)
  └── DashboardState (session_key for anonymous)
        ├── active_upload → DatasetUpload
        └── blueprint_override (JSON)

DatasetUpload (owner, session_key, name, description, source_type, file, source_url, stored_path, row_count, ai_blueprint, status, error_message, is_archived)
IngestionJob (source, status, details)
```

**State & Ownership persistence:**
- Authenticated users: `DashboardState` and `DatasetUpload` keyed by `user` / `owner`
- Anonymous visitors: `DashboardState` and `DatasetUpload` keyed by Django `session_key`
- Resolved uploads: `resolve_active_upload` ensures active custom uploads are fully scoped to the requesting user/session, falling back safely to the global read-only seed dataset.

---

## 8. AI Integration

| Function | NVIDIA endpoint | Fallback |
|----------|-----------------|----------|
| Chat | `POST /v1/chat/completions` | Dataset-aware local message |
| Blueprint | Same | Heuristic column selection |
| Dataset brief | Same | Basic statistics message |

Configuration: `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL` in `.env`.

---

## 9. Security Controls (Phase 1.5)

| Control | Status |
|---------|--------|
| CSRF on POST endpoints | Enabled (frontend sends `X-CSRFToken`) |
| Chat session ownership (authenticated) | Enforced |
| SSRF guard (scheme, host, IP literal, DNS resolve) | **Implemented** (ADR-018) |
| SSRF via HTTP redirect chains | **Not implemented** (TD-019) |
| PostgreSQL table name validation | Enforced |
| Upload error message sanitization | Enforced |
| API authentication / rate limiting | **Not implemented** |
| Production config validation | **Implemented** (ADR-019) |
| Anonymous chat session isolation | **Not implemented** |

See `docs/DEPLOYMENT.md` and `docs/SECURITY.md`.

---

## 10. Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `DJANGO_ENV` | `development` | `development` \| `staging` \| `production` |
| `DEBUG` | `True` (dev) / `False` (staging/prod) | Django debug mode |
| `DJANGO_SECRET_KEY` | insecure dev fallback | Session signing |
| `LOG_LEVEL` | `INFO` | Application logging |
| `NVIDIA_API_KEY` | empty | AI features |
| `ANALYTICS_SOURCE` | `csv` | `csv` or `postgres` |
| `ANALYTICS_TABLE` | `analytics_sales` | PostgreSQL table name |

See `.env.example` for full list.

---

## 11. Testing

```bash
python manage.py check
python manage.py test analytics_assistant   # 31 tests
```

Test categories: schema, URL safety, analytics engines, dataset pipeline, chat scoping, API integration.

---

## 12. Related Documents

| Document | Purpose |
|----------|---------|
| `docs/STABILIZATION.md` | ADR log (Iterations 1–3) |
| `docs/TECHNICAL_DEBT.md` | Known issues register |
| `docs/PHASE1_RETROSPECTIVE.md` | Phase 1 summary |
| `docs/SECURITY.md` | SSRF and production security notes |

---

## 13. Phase 1 Module Count

| Category | Files |
|----------|-------|
| Backend Python modules | 22 (excl. migrations/tests) |
| Migrations | 4 |
| Frontend assets | 3 (HTML, CSS, JS) |
| Documentation | 5 |
| **Total project files** | ~47 |
