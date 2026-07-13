# Technical Debt Register — Phase 1 RC

**Project:** Nexa Analytics AI Assistant  
**Register date:** 2026-07-13  
**Status:** Active — review before Phase 2 kickoff

Severity scale: **Critical** · **High** · **Medium** · **Low**

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 2 |
| High | 4 |
| Medium | 7 |
| Low | 5 |
| **Total** | **18** |

---

## Register

### TD-001 — DNS-resolved SSRF on URL ingestion

| Field | Value |
|-------|-------|
| **Severity** | Critical |
| **Area** | Security · `url_safety.py` |
| **Description** | URL guard blocks IP literals and known bad hostnames but does not resolve DNS. A public hostname pointing to a private IP (e.g. `http://evil.example` → `10.0.0.1`) may bypass the guard. |
| **Risk** | Internal network probing, cloud metadata access in production |
| **Proposed resolution** | Resolve hostname before fetch; reject if any resolved address is private/link-local/reserved. Consider allowlist mode for enterprise. |
| **Phase** | Phase 1.5 (pre-Phase 2 gate) or Phase 2 M1 |
| **Effort** | Small–Medium |

---

### TD-002 — Production secrets and DEBUG defaults

| Field | Value |
|-------|-------|
| **Severity** | Critical |
| **Area** | Config · `config/settings.py` |
| **Description** | `DEBUG=True` and an insecure default `SECRET_KEY` ship in settings. Suitable for dev only. |
| **Risk** | Full stack trace exposure, session forgery if deployed as-is |
| **Proposed resolution** | Fail startup when `DEBUG=True` and `SECRET_KEY` is default in non-dev env; document production checklist; require env vars in deployment. |
| **Phase** | Phase 1.5 (deploy gate) |
| **Effort** | Small |

---

### TD-003 — Anonymous chat session not bound to browser session

| Field | Value |
|-------|-------|
| **Severity** | High |
| **Area** | Security · `models.py` · `chat_service.py` |
| **Description** | `ChatSession` has no `session_key`. Any anonymous client knowing a `session_id` can resume another visitor's chat. |
| **Risk** | Conversation hijacking for unauthenticated users |
| **Proposed resolution** | Add `session_key` to `ChatSession`; bind on create; validate on resume. Migration required. |
| **Phase** | Phase 1.5 or Phase 2 M1 |
| **Effort** | Small |

---

### TD-004 — No API authentication or rate limiting

| Field | Value |
|-------|-------|
| **Severity** | High |
| **Area** | Security · `views.py` |
| **Description** | All endpoints are public. No throttling on chat, upload, or URL ingestion. |
| **Risk** | Abuse, cost explosion (NVIDIA API), DoS via large uploads |
| **Proposed resolution** | DRF authentication classes, per-IP rate limits (django-ratelimit or API gateway), optional API keys for Phase 2 multi-tenant. |
| **Phase** | Phase 2 M2 |
| **Effort** | Medium |

---

### TD-005 — Unpinned Python dependencies

| Field | Value |
|-------|-------|
| **Severity** | High |
| **Area** | DevOps · `requirements.txt` |
| **Description** | Dependencies listed without version pins. Reproducible builds not guaranteed. |
| **Risk** | CI/production breakage on upstream releases |
| **Proposed resolution** | `pip freeze` or `pip-tools` compile; commit `requirements.lock`; renovate/dependabot. |
| **Phase** | Phase 1.5 |
| **Effort** | Small |

---

### TD-006 — No CI/CD pipeline

| Field | Value |
|-------|-------|
| **Severity** | High |
| **Area** | DevOps |
| **Description** | Tests run manually only. No automated check on commit/PR. |
| **Risk** | Regressions merge undetected |
| **Proposed resolution** | GitHub Actions: `check`, `test`, lint; optional coverage gate. |
| **Phase** | Phase 1.5 |
| **Effort** | Small |

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
| **Severity** | Low |
| **Area** | `dataset_pipeline.py` · `data_sources.py` |
| **Description** | `DEFAULT_SEED_PATH` and `_SEED_PATH` both reference `data/sales_data.csv` independently. |
| **Risk** | Drift if path changes in one file only |
| **Proposed resolution** | Single constant in `dataset_pipeline.py`; `data_sources` imports it. |
| **Phase** | Phase 1.5 |
| **Effort** | Trivial |

---

### TD-018 — Test coverage gaps

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Area** | `tests.py` |
| **Description** | 26 tests cover critical paths but lack: file upload E2E, ads-mode payload, blueprint save, engine unit tests in isolation. |
| **Risk** | Regressions in upload flow or ads analytics |
| **Proposed resolution** | Add fixture-based upload test; ads CSV golden-file test; split tests into package. |
| **Phase** | Phase 1.5 / Phase 2 M1 |
| **Effort** | Medium |

---

## Debt Paydown Priority (Recommended)

```
Phase 1.5 (pre-Phase 2 gate)
  TD-002, TD-005, TD-006, TD-017  → deploy readiness
  TD-001, TD-003                   → security closure

Phase 2 early
  TD-008, TD-004, TD-010           → enterprise foundation
  TD-007, TD-011, TD-012           → data platform

Phase 2 later
  TD-009, TD-016, TD-015, TD-014   → product completeness
```

---

## Change Log

| Date | Change |
|------|--------|
| 2026-07-13 | Initial register at Phase 1 RC |
