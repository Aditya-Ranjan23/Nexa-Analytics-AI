# Nexa Analytics — Stabilization Log

This document records architectural decisions made during the pre-production stabilization phase.

## Iteration 1 — Foundation Hardening

### ADR-001: Fix `_time_series_rows` empty return contract

**Decision:** Return `([], "")` instead of `[]` when no valid time-series rows exist.

**Why:** Callers unpack `(rows, x_key)`. Returning a bare list caused `ValueError` on datasets with date-like columns but no parseable values (e.g. HR data with non-date fields named `YearsAtCompany`).

**Impact:** Prevents dashboard API 500s on generic datasets. No API shape change.

---

### ADR-002: Centralize dataset profiling

**Decision:** Extract `profile_for_blueprint()` into `analytics_assistant/dataset_profile.py`.

**Why:** The same column profiling logic lived in `views.py` for blueprint generation. Single source of truth reduces drift.

**Impact:** Views and blueprint generation share one helper. Future org/multi-tenant profiling extends here.

---

### ADR-003: Consolidate upload activation flow

**Decision:** Introduce `_persist_dataset_activation()` in views for file and URL ingestion success paths.

**Why:** `dataset_upload` and `dataset_upload_link` duplicated 20+ lines of activation, state update, and response building.

**Impact:** One code path for activating datasets. Failures still handled per-endpoint with logging.

---

### ADR-004: Structured logging via Django `LOGGING`

**Decision:** Add `LOGGING` config in `config/settings.py` with `LOG_LEVEL` env override. Instrument `analytics_assistant` views, services, analytics, and data_sources.

**Why:** Zero logging existed. Production debugging and incident response require structured server-side logs without exposing secrets to the client.

**Impact:** Console logs in dev; ready for file/JSON handlers in deployment.

---

### ADR-005: Chat session ownership checks

**Decision:** Reject chat `session_id` reuse when the session belongs to a different authenticated user, or when an anonymous caller targets an authenticated user's session.

**Why:** Session IDs were globally accessible — a stability and security defect.

**Impact:** Authenticated users are isolated. Anonymous session isolation remains a known gap (see risks).

---

### ADR-006: PostgreSQL table identifier validation

**Decision:** Validate `ANALYTICS_TABLE` against `^[A-Za-z_][A-Za-z0-9_]*$` and quote the identifier in SQL.

**Why:** Table name comes from env config. Validation prevents misconfiguration and reduces injection risk if env is compromised.

**Impact:** Invalid table names fail fast with a logged error.

---

### ADR-007: Baseline automated tests

**Decision:** Add Django tests covering schema validation, role normalization, time-series edge case, analytics payload smoke test, and chat session scoping.

**Why:** `tests.py` was empty. Critical paths need regression protection before further refactors.

**Impact:** `python manage.py test analytics_assistant` validates core stability.

---

## Iteration 2 — API Layer Hardening

### ADR-008: Thin views with service modules

**Decision:** Extract upload and chat orchestration into `upload_service.py` and `chat_service.py`. Move request helpers to `request_context.py`.

**Why:** `views.py` mixed HTTP handling, file I/O, persistence, and business rules (~420 lines). Services are testable without HTTP and views become thin controllers.

**Impact:** Views delegate to services. No API response shape changes for successful requests.

---

### ADR-009: DRF serializers for write endpoints

**Decision:** Add `serializers.py` with validators for chat, URL upload, blueprint, and ingestion endpoints.

**Why:** Manual `request.data` parsing had no length limits, type checks, or consistent 400 responses.

**Impact:** Invalid input returns structured serializer errors. Chat empty-message errors use `{"message": [...]}` instead of `{"detail": ...}`.

---

### ADR-010: SSRF guard for URL ingestion

**Decision:** Add `url_safety.validate_public_http_url()` — blocks non-http(s) schemes, localhost, `.local`/`.internal` hosts, and private/reserved IP literals.

**Why:** `/api/data/upload-link/` could fetch internal network resources (production blocker).

**Impact:** Private URLs rejected before outbound request. ponytail: hostname DNS resolution not checked; upgrade path is resolved-IP validation.

---

### ADR-011: Role-scoped KPI filtering

**Decision:** Add `filter_kpi_cards_for_role()` in `roles.py`; apply in analytics payload and mirror in `dashboard.js`.

**Why:** API returned `widgets` but UI rendered all KPI cards — role personalization appeared broken.

**Impact:** Ads datasets show role-relevant KPIs. Generic datasets keep all cards when no widget keys match (fallback).

---

### ADR-012: Safer client error messages on upload failures

**Decision:** Generic upload/URL ingestion exceptions return user-safe messages; full trace logged server-side.

**Why:** Raw exception strings could leak paths or internal details.

**Impact:** Clients see `"Upload failed. Please check the file format."` instead of stack-internal messages.

---

### ADR-013: API integration test suite

**Decision:** Add `ApiIntegrationTests` covering health, summary, chat validation, SSRF block, blueprint, and upload guards.

**Why:** Iteration 1 tests were unit-level only; HTTP layer regressions were unguarded.

**Impact:** 22 tests total (was 10).

---

### ADR-014: Generic-safe NVIDIA fallback messages

**Decision:** Make `_local_fallback()` dataset-mode aware; never assume ads KPI keys exist.

**Why:** Chat on generic datasets (e.g. HR data) crashed with `KeyError: revenue_total` when NVIDIA key was unset. Exposed during integration testing after KPI filtering changes.

**Impact:** Fallback chat works for all dataset modes without NVIDIA configured.

---

## Iteration 3 — Analytics Decomposition + Unified Dataset Pipeline

### ADR-015: Decompose analytics monolith into engines

**Decision:** Split `analytics.py` into focused modules:
- `column_utils.py` — column detection and metric ranking
- `kpi_engine.py` — KPI card construction
- `chart_engine.py` — chart specs and time-series aggregation
- `insights_engine.py` — auto-detected insight cards
- `analytics.py` — thin orchestration facade (`build_analytics_payload`)

**Why:** The 820-line monolith mixed unrelated concerns and blocked safe refactors.

**Impact:** Same public API (`build_analytics_payload`). Internal imports updated; tests import `time_series_rows` from `chart_engine`.

---

### ADR-016: Unified dataset pipeline (single load path)

**Decision:** Add `dataset_pipeline.py` as the sole data resolution layer:
1. Explicit or latest `DatasetUpload.stored_path` (media)
2. PostgreSQL when `ANALYTICS_SOURCE=postgres`
3. Read-only seed CSV at `data/sales_data.csv`

Remove upload-time copy to `data/sales_data.csv`.

**Why:** Dual writes (`media/datasets/` + `sales_data.csv`) risked drift. Upload activation and analytics reads used different paths.

**Impact:** Uploads persist only under `media/datasets/`. Seed CSV is never overwritten. `DashboardState.active_upload` and latest processed upload drive resolution.

---

### ADR-017: Consolidate blueprint resolution in pipeline

**Decision:** Move `active_blueprint()` into `dataset_pipeline.py` alongside upload resolution.

**Why:** Blueprint and dataframe must reference the same upload record.

**Impact:** `analytics.py` no longer queries `DatasetUpload` directly for blueprints.

---

## Deferred (Intentionally Not Changed)

| Item | Reason |
|------|--------|
| Split `views.py` into service layer | **Done in Iteration 2** |
| `analytics.py` monolith split | **Done in Iteration 3** |
| Dual dataset storage | **Done in Iteration 3** |
| Multi-tenant / org model | Out of scope for stabilization |
| Replace SQLite with PostgreSQL | Config-ready; migration is ops task |
| Frontend XSS hardening for insight headlines | Low risk (server-generated); revisit with auth |
| Anonymous chat session binding to Django session key | Requires model migration; tracked as risk |
| DNS-resolved SSRF protection | **Done** — Phase 1.5 Iter 1 (`docs/SECURITY.md`) |
| SSRF via HTTP redirects | Tracked as TD-019 |

---

## Phase 1.5 — Deployment Hardening

### ADR-019: Production environment validation

**Decision:** Add `config/env_validation.py` with `validate_deployment_env()`. Call at end of `settings.py`. Add `settings_production.py` entrypoint.

**Why:** Insecure `DEBUG` and default `SECRET_KEY` allowed accidental production deploy (TD-002).

**Impact:** Development unchanged (`DJANGO_ENV=development` default). Staging/production fail fast on misconfiguration.

---

### ADR-018: DNS-aware SSRF validation

**Decision:** Resolve URL hostnames via `socket.getaddrinfo` before fetch; reject if any resolved address is private, loopback, link-local, reserved, or multicast. Block embedded URL credentials.

**Why:** IP-literal and hostname blocklists alone allowed DNS rebinding to internal networks (TD-001).

**Impact:** `validate_public_http_url()` accepts optional `resolver` for tests. Redirect chains remain unvalidated (TD-019).

---

## Phase 1 Closure

Phase 1 stabilization is **complete** (Release Candidate).

| Document | Purpose |
|----------|---------|
| `docs/ARCHITECTURE.md` | Official architecture |
| `docs/TECHNICAL_DEBT.md` | 18 known issues with severity |
| `docs/PHASE1_RETROSPECTIVE.md` | Objectives, changes, sign-off |
| `docs/PHASE2_ROADMAP.md` | Next-phase milestones |

---

## Verification Commands

```bash
python manage.py check
python manage.py test analytics_assistant
python manage.py runserver
```
