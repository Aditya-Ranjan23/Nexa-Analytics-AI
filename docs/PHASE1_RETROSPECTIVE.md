# Phase 1 Retrospective — Nexa Analytics AI Assistant

**Phase:** Stabilization (pre-production hardening)  
**Duration:** 3 iterations  
**Release candidate date:** 2026-07-13  
**Verdict:** **Phase 1 objectives achieved** — suitable as internal/demo RC; not production-deploy without Phase 1.5 security gates.

---

## 1. Phase 1 Objectives

| Objective | Target | Result |
|-----------|--------|--------|
| Review complete codebase | Full audit | Done — 3 iterations, 17 ADRs |
| Identify and fix bugs | Critical paths stable | Done — time-series crash, chat fallback KeyError |
| Reduce technical debt | Measurable structural improvement | Done — see §3 |
| Improve maintainability | Modular, testable layers | Done — services + engines + pipeline |
| Improve security | Close obvious holes | Partial — SSRF partial, session scoping partial |
| Improve testing | Automated regression suite | Done — 0 → 26 tests |
| Preserve functionality | No feature regressions | Done — all APIs unchanged |
| Document decisions | ADR trail | Done — `STABILIZATION.md` |

---

## 2. Complete Change Log (Phase 1)

### Iteration 1 — Foundation Hardening

| Change | Files touched |
|--------|---------------|
| Fix `_time_series_rows` empty return bug | `analytics.py` |
| Extract `profile_for_blueprint()` | `dataset_profile.py` (new), `views.py` |
| Consolidate upload activation | `views.py` |
| Add `LOGGING` config + instrumentation | `settings.py`, `views.py`, `services.py`, `analytics.py`, `data_sources.py` |
| Chat session ownership for auth users | `views.py` |
| PostgreSQL table name validation | `data_sources.py` |
| Baseline tests (10) | `tests.py` |
| `.env.example` | new |
| ADR documentation | `docs/STABILIZATION.md` (new) |

### Iteration 2 — API Layer Hardening

| Change | Files touched |
|--------|---------------|
| Extract `chat_service.py`, `upload_service.py` | new modules; slimmed `views.py` |
| Extract `request_context.py` | new |
| DRF `serializers.py` | new |
| SSRF guard `url_safety.py` | new |
| Role KPI filtering | `roles.py`, `analytics.py`, `dashboard.js` |
| Safer upload error messages | `views.py` |
| Generic-safe NVIDIA fallback | `services.py` |
| API integration tests (+12) | `tests.py` |

### Iteration 3 — Analytics Decomposition + Unified Pipeline

| Change | Files touched |
|--------|---------------|
| Split analytics into engines | `kpi_engine.py`, `chart_engine.py`, `insights_engine.py`, `column_utils.py` (new); `analytics.py` rewritten as facade |
| Unified `dataset_pipeline.py` | new; removed dual write to `sales_data.csv` |
| Blueprint resolution in pipeline | `dataset_pipeline.py`; removed from `analytics.py` |
| Pipeline tests (+4) | `tests.py` |
| Architecture docs | `docs/ARCHITECTURE.md` |

### Documentation (this closure)

| Document | Purpose |
|----------|---------|
| `docs/ARCHITECTURE.md` | Official architecture (updated RC) |
| `docs/TECHNICAL_DEBT.md` | Debt register (18 items) |
| `docs/PHASE1_RETROSPECTIVE.md` | This document |
| `docs/PHASE2_ROADMAP.md` | Next-phase plan |

---

## 3. Major Architectural Improvements

### Before Phase 1

```
views.py (~420 lines)
  ├── HTTP + file I/O + chat + upload + state + analytics calls

analytics.py (~820 lines)
  ├── KPIs + charts + insights + loading + blueprint + payload

Dual data path:
  upload → media/datasets/ AND data/sales_data.csv
  read   → upload path OR sales_data.csv (could diverge)

tests.py: empty
logging: none
```

### After Phase 1

```
views.py (~199 lines)          → thin HTTP controllers
serializers.py                 → input validation
request_context.py             → role + dashboard state
chat_service.py                → chat orchestration
upload_service.py              → ingestion orchestration
url_safety.py                  → SSRF guard

analytics.py (~199 lines)      → facade only
kpi_engine.py                  → KPI logic
chart_engine.py                → chart logic
insights_engine.py             → insight logic
column_utils.py                → shared column helpers
dataset_pipeline.py            → single data resolution path

tests.py: 26 tests
LOGGING: structured, env-configurable
```

**Quantified improvement:**

| Metric | Before | After |
|--------|--------|-------|
| Largest backend file | ~820 lines | ~317 lines (`chart_engine.py`) |
| Test count | 0 | 26 |
| ADRs documented | 0 | 17 |
| Data write paths on upload | 2 | 1 |
| Service modules | 0 | 4 |

---

## 4. Security Improvements

| Item | Before | After |
|------|--------|-------|
| Chat session hijack (auth users) | Vulnerable | Mitigated (ownership check) |
| Chat session hijack (anonymous) | Vulnerable | **Open** (TD-003) |
| URL ingestion SSRF | Unprotected | Partial (IP literal + hostname blocklist) |
| DNS SSRF | Unprotected | **Open** (TD-001) |
| SQL table injection via env | Possible | Mitigated (regex + quoting) |
| Error message info leak | Raw exceptions to client | Sanitized on upload paths |
| API auth / rate limits | None | **Open** (TD-004) |
| Production secret handling | Insecure defaults | **Open** (TD-002) |

**Net assessment:** Meaningful hardening for a class project / internal demo. **Not production-ready** without TD-001, TD-002, TD-003, TD-004.

---

## 5. Testing Status

```
python manage.py check              → PASS
python manage.py test analytics_assistant → 26/26 PASS
```

| Test class | Tests | Coverage area |
|------------|-------|---------------|
| SchemaTests | 3 | Column validation, ads/generic mode |
| RoleTests | 4 | Normalization, widgets, KPI filter |
| UrlSafetyTests | 3 | SSRF guard |
| AnalyticsEngineTests | 2 | Time series, profiling |
| DatasetPipelineTests | 4 | Seed load, fallback, upload resolution |
| AnalyticsPayloadTests | 1 | End-to-end payload smoke |
| ChatSessionScopeTests | 2 | Auth session isolation |
| ApiIntegrationTests | 7 | HTTP layer regression |

**Gaps (TD-018):** No file upload E2E, no ads-mode golden test, no isolated engine unit test package.

---

## 6. Remaining Risks

| Risk | Likelihood | Impact | Mitigation path |
|------|------------|--------|-----------------|
| DNS SSRF in production | Medium | High | TD-001 before public deploy |
| Anonymous chat hijack | Medium | Medium | TD-003 |
| NVIDIA API abuse (no rate limit) | High | Medium | TD-004 |
| Dependency drift breaks build | Medium | Medium | TD-005, TD-006 |
| SQLite lock under concurrent users | Low (demo) / High (prod) | High | TD-007 |
| Misleading ingestion API | Low | Low | TD-009 |

---

## 7. What We Deliberately Did Not Change

- Multi-tenant / organization model
- New AI providers beyond NVIDIA
- Real ingestion connectors (Supabase, Firebase, etc.)
- User authentication UI (Django auth exists but dashboard is anonymous-first)
- Frontend redesign
- PostgreSQL as default app database
- CI/CD pipeline
- Dependency pinning

These are scoped for Phase 2 or Phase 1.5 gates.

---

## 8. Lessons Learned

1. **Integration tests catch facade bugs** — KPI filtering exposed `KeyError` in chat fallback only under HTTP test path.
2. **Unified data path early prevents subtle drift** — dual `sales_data.csv` write was a latent consistency bug.
3. **Thin views + services enable safe refactors** — analytics decomposition was possible because views no longer owned business logic.
4. **Document as you go** — ADR log made this retrospective straightforward.
5. **Security needs explicit closure criteria** — partial SSRF guard is worse than documented partial; debt register is essential.

---

## 9. Phase 1 Sign-Off Criteria

| Criterion | Met? |
|-----------|------|
| No known crash bugs on default flows | Yes |
| Automated test suite | Yes (26) |
| Documented architecture | Yes |
| Documented technical debt | Yes |
| Modular codebase | Yes |
| Production deploy ready | **No** — see TD-001, TD-002, TD-003, TD-004 |

**Recommendation:** Treat current state as **Phase 1 RC**. Complete Phase 1.5 security/deploy gates before Phase 2 feature work or public deployment.
