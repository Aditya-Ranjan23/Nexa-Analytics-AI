# Technical Debt Register — Phase 1 RC

**Project:** Nexa Analytics AI Assistant  
**Register date:** 2026-07-13  
**Status:** Active — review before Phase 2 kickoff

Severity scale: **Critical** · **High** · **Medium** · **Low**

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 6 |
| Low | 4 |
| **Total (open)** | **10** |
| **Closed (Phase 1.5)** | **7 (TD-001, TD-002, TD-003, TD-005, TD-006, TD-017, TD-019)** |

---

## Register

### TD-001 — DNS-resolved SSRF on URL ingestion

| Field | Value |
|-------|-------|
| **Severity** | ~~Critical~~ **Resolved (Phase 1.5)** |
| **Area** | Security · `url_safety.py` |
| **Description** | URL guard now resolves hostnames and rejects private/reserved resolved addresses. Embedded credentials blocked. |
| **Residual risk** | HTTP redirect chains not validated (see TD-019) |
| **Resolved** | 2026-07-13 — Phase 1.5 Iteration 1 |

---

### TD-019 — SSRF via HTTP redirects

| Field | Value |
|-------|-------|
| **Severity** | ~~Medium~~ **Resolved (Phase 1.5)** |
| **Area** | Security · `upload_service.py` · `url_safety.py` |
| **Description** | `build_safe_session()` attaches `_redirect_hook` to every outbound request; each redirect destination is re-validated via `validate_public_http_url`. |
| **Resolution** | `url_safety.build_safe_session()` — Phase 1.5 |
| **Resolved** | 2026-07-13 — Phase 1.5 |

---

### TD-001-ARCHIVED — DNS-resolved SSRF (original)

| Field | Value |
|-------|-------|
| **Severity** | Critical (closed) |
| **Original description** | URL guard blocked IP literals but not hostname → private IP resolution. |
| **Resolution** | `validate_hostname_resolves_public()` in `url_safety.py` |

---

### TD-002 — Production secrets and DEBUG defaults

| Field | Value |
|-------|-------|
| **Severity** | ~~Critical~~ **Resolved (Phase 1.5)** |
| **Area** | Config · `config/env_validation.py` |
| **Description** | `validate_deployment_env()` fails startup when `DJANGO_ENV` is staging/production with `DEBUG=True`, insecure `SECRET_KEY`, or wildcard `ALLOWED_HOSTS`. |
| **Resolution** | `config/settings_production.py`, `docs/DEPLOYMENT.md` |
| **Resolved** | 2026-07-13 — Phase 1.5 Iteration 2 |

---

### TD-002-ARCHIVED — Production secrets (original)

| Field | Value |
|-------|-------|
| **Severity** | Critical (closed) |
| **Original description** | `DEBUG=True` and insecure default `SECRET_KEY` shipped without guard. |

---

### TD-003 — Anonymous chat session not bound to browser session

| Field | Value |
|-------|-------|
| **Severity** | ~~High~~ **Resolved (Phase 1.5)** |
| **Area** | Security · `models.py` · `chat_service.py` · `request_context.py` |
| **Description** | `ChatSession` now stores `session_key`. Anonymous sessions are bound on create and validated on resume. |
| **Resolution** | Migration `0005_chatsession_session_key` · `session_belongs_to_request` updated |
| **Resolved** | 2026-07-13 — Phase 1.5 |

---

### TD-004 — No API authentication or rate limiting

| Field | Value |
|-------|-------|
| **Severity** | High (partial — rate limiting resolved) |
| **Area** | Security · `views.py` · `throttles.py` |
| **Description** | **Rate limiting** added in Phase 1.5 via DRF throttle classes on chat, upload, and upload-link endpoints. API **authentication** (tokens, API keys) remains Phase 2. |
| **Remaining risk** | Endpoints remain publicly accessible without auth tokens |
| **Proposed resolution** | DRF authentication classes, optional API keys for Phase 2 multi-tenant. |
| **Phase** | Phase 2 M2 |
| **Effort** | Medium |

---

### TD-005 — Unpinned Python dependencies

| Field | Value |
|-------|-------|
| **Severity** | ~~High~~ **Resolved (Phase 1.5)** |
| **Area** | DevOps · `requirements.txt` |
| **Description** | All 6 runtime dependencies pinned to exact versions. Reproducible builds now guaranteed. |
| **Resolution** | `requirements.txt` pinned — Phase 1.5 |
| **Resolved** | 2026-07-13 — Phase 1.5 |

---

### TD-006 — No CI/CD pipeline

| Field | Value |
|-------|-------|
| **Severity** | ~~High~~ **Resolved (Phase 1.5)** |
| **Area** | DevOps |
| **Description** | GitHub Actions CI at `.github/workflows/ci.yml` runs Django checks, migrations, 57 tests, flake8 lint, and deployment checks on every push/PR. |
| **Resolution** | `.github/workflows/ci.yml` — Phase 1.5 |
| **Resolved** | 2026-07-13 — Phase 1.5 |

---

### TD-007 — SQLite as default database

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Area** | Infrastructure |
| **Description** | Single-file SQLite unsuitable for multi-worker production or concurrent writes. |
| **Risk** | Lock contention, data loss under load |
| **Proposed resolution** | PostgreSQL for app DB in production; keep SQLite for local dev. Document migration path. |
| **Phase** | Phase 2 M3 |
| **Effort** | Medium |

---

### TD-008 — No multi-tenant / organization model

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Area** | Architecture |
| **Description** | Single global dataset namespace. `DashboardState` per user/session only. No org isolation. |
| **Risk** | Blocks enterprise multi-customer deployment |
| **Proposed resolution** | Introduce `Organization` model; scope uploads, state, chat, blueprints per org. |
| **Phase** | Phase 2 M1 (foundational) |
| **Effort** | Large |

---

### TD-009 — Ingestion job is a stub

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Area** | `views.py` · `run_ingestion` |
| **Description** | `/api/ingestion/run/` logs row count only. No scheduler, connector sync, or retry logic. |
| **Risk** | Misleading API contract for integrators |
| **Proposed resolution** | Implement real ingestion queue (Celery/django-q) or rename/document as health sync; add connectors in Phase 2. |
| **Phase** | Phase 2 M4 |
| **Effort** | Medium–Large |

---

### TD-010 — Single AI provider (NVIDIA only)

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Area** | `services.py` |
| **Description** | AI calls hardcoded to NVIDIA chat completions. No provider abstraction or failover. |
| **Risk** | Vendor lock-in, outage = no AI |
| **Proposed resolution** | `AIProvider` interface; adapters for NVIDIA, OpenAI, local Ollama; config-driven selection. |
| **Phase** | Phase 2 M2 |
| **Effort** | Medium |

---

### TD-011 — Pandas date-parsing warnings on seed data

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Area** | `chart_engine.py` · HR seed dataset |
| **Description** | Columns like `YearsAtCompany` match date heuristics; pandas emits format inference warnings. |
| **Risk** | Noisy logs; potential mis-charting |
| **Proposed resolution** | Stricter date column validation (parse sample before accepting); rename seed columns; suppress only after fix. |
| **Phase** | Phase 2 M1 |
| **Effort** | Small |

---

### TD-012 — Seed dataset naming mismatch

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Area** | `data/sales_data.csv` |
| **Description** | File named `sales_data.csv` contains HR analytics data. Confusing for demos and docs. |
| **Risk** | Developer/user confusion |
| **Proposed resolution** | Rename to `hr_analytics_seed.csv`; update pipeline constant; keep backward compat alias or migration note. |
| **Phase** | Phase 2 M1 |
| **Effort** | Small |

---

### TD-013 — Frontend insight cards use unsanitized innerHTML

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Area** | `dashboard.js` |
| **Description** | Insight headlines/details rendered via template strings into `innerHTML`. Content is server-generated today. |
| **Risk** | XSS if server ever reflects user input in insights |
| **Proposed resolution** | Use `textContent` or DOMPurify for insight cards (already used for chat markdown). |
| **Phase** | Phase 2 M1 |
| **Effort** | Small |

---

### TD-014 — Chat error response shape inconsistency

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Area** | `serializers.py` · `views.py` |
| **Description** | Chat validation errors return `{"message": [...]}`; other endpoints use `{"detail": ...}`. |
| **Risk** | Frontend error handling complexity |
| **Proposed resolution** | Standardize on DRF error envelope or document per-endpoint contracts in OpenAPI. |
| **Phase** | Phase 2 M2 |
| **Effort** | Small |

---

### TD-015 — No OpenAPI / API documentation

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Area** | API |
| **Description** | Endpoints documented in README only. No auto-generated schema. |
| **Risk** | Integrator friction |
| **Proposed resolution** | Add `drf-spectacular` or similar; publish schema at `/api/schema/`. |
| **Phase** | Phase 2 M2 |
| **Effort** | Small |

---

### TD-016 — Role widgets partially implemented

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Area** | `roles.py` · frontend |
| **Description** | Non-KPI widgets (`trend_summary`, `top_channels`, `campaign_actions`) are defined but not rendered as distinct UI components. |
| **Risk** | Incomplete role personalization |
| **Proposed resolution** | Map widget IDs to dashboard sections; hide/show chart groups and insight panels by role. |
| **Phase** | Phase 2 M3 |
| **Effort** | Medium |

---

### TD-017 — Duplicate seed path constants

| Field | Value |
|-------|-------|
| **Severity** | ~~Low~~ **Resolved (Phase 1.5)** |
| **Area** | `data_sources.py` · `dataset_pipeline.py` |
| **Description** | `data_sources.py` now imports `DEFAULT_SEED_PATH` from `dataset_pipeline.py`. Single source of truth. |
| **Resolution** | Import refactor — Phase 1.5 |
| **Resolved** | 2026-07-13 — Phase 1.5 |

---

### TD-018 — Test coverage gaps

| Field | Value |
|-------|-------|
| **Severity** | ~~Medium~~ **Substantially resolved (Phase 1.5)** |
| **Area** | `tests.py` |
| **Description** | Phase 1.5 added 20 new tests (57 total): SSRF redirect, upload size/MIME, anonymous session isolation, health check, blueprint save/load, E2E CSV upload. |
| **Residual gaps** | Ads-mode payload golden-file test; engine isolation tests; coverage reporting in CI |
| **Phase** | Phase 2 M1 |
| **Effort** | Small |

---

## Debt Paydown Priority (Recommended)

```
Phase 1.5 — COMPLETED
  TD-001  → DNS-aware SSRF (resolved)
  TD-002  → Production secrets / DEBUG (resolved)
  TD-003  → Anonymous session isolation (resolved)
  TD-005  → Dependency pinning (resolved)
  TD-006  → CI/CD pipeline (resolved)
  TD-017  → Seed path deduplication (resolved)
  TD-019  → SSRF redirect protection (resolved)

Phase 2 early (TD-004 partially addressed: rate limiting done, auth pending)
  TD-008, TD-004, TD-010  → enterprise foundation
  TD-007, TD-011, TD-012  → data platform

Phase 2 later
  TD-009, TD-016, TD-015, TD-014  → product completeness
  TD-013, TD-018 (residual)       → frontend security, test coverage
```

---

## Change Log

| Date | Change |
|------|--------|
| 2026-07-13 | Initial register at Phase 1 RC |
| 2026-07-13 | Phase 1.5 — Closed TD-001, TD-002 (env validation + SSRF DNS) |
| 2026-07-13 | Phase 1.5 — Closed TD-003, TD-005, TD-006, TD-017, TD-019 (session isolation, deps, CI, path dedup, redirect SSRF) |
| 2026-07-13 | Phase 1.5 — TD-004 partially resolved (rate limiting done; API auth deferred to Phase 2) |
| 2026-07-13 | Phase 1.5 — TD-018 substantially resolved (57 tests; residual gaps deferred to Phase 2 M1) |
