# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] — 2026-07-13 — Phase 1.5 Developer Preview

### Security

- **SSRF redirect protection** (TD-019 closed)
  - `build_safe_session()` in `url_safety.py` attaches a redirect validation hook
  - Every HTTP redirect hop is re-validated by the same DNS-aware SSRF guard
  - Blocks redirect chains that lead to private/reserved IP ranges

- **Anonymous session isolation** (TD-003 closed)
  - `ChatSession` now stores `session_key` (Django session key) for anonymous users
  - `session_belongs_to_request()` validates session key on resume
  - Migration `0005_chatsession_session_key` adds indexed field

- **Secure upload validation**
  - File size limit: configurable `MAX_UPLOAD_BYTES` (default 25 MB)
  - Django-level enforcement via `DATA_UPLOAD_MAX_MEMORY_SIZE`
  - MIME type validation via `mimetypes.guess_type()` after save
  - Applied to both file uploads and URL-ingested content

- **API rate limiting**
  - DRF throttle classes applied to all resource-intensive endpoints
  - Chat: 20 req/min anonymous, 40 req/min authenticated
  - Upload: 10 req/min anonymous, 20 req/min authenticated
  - All rates configurable via environment variables

- **Production environment validation** (TD-002 closed — Phase 1.5 early iteration)
  - Fail-fast on `DEBUG=True`, weak `SECRET_KEY`, or wildcard `ALLOWED_HOSTS` in production

- **DNS-aware SSRF protection** (TD-001 closed — Phase 1.5 early iteration)
  - Hostname resolution validates all returned A/AAAA records

### Deployment

- **Pinned dependencies** (TD-005 closed)
  - `requirements.txt` now pins all 6 runtime dependencies with exact versions
  - Reproducible builds guaranteed

- **Improved `.env.example`**
  - All configurable settings documented with examples
  - Rate limit and upload size knobs added

- **Enhanced health check** (`/health/`)
  - DB liveness ping via `SELECT 1`
  - Returns `503` on DB failure (suitable for k8s readiness probes)
  - Returns `version: "0.2.0"` in response body

- **Improved `.gitignore`**
  - Covers virtual environments, `media/`, IDE files, OS artifacts

### CI/CD

- **GitHub Actions workflow** (TD-006 closed)
  - Path: `.github/workflows/ci.yml`
  - Jobs: `test` (Django checks, migrations, test suite, flake8) + `security-check` (deploy checks)
  - Triggers on push/PR to `main` and `develop`

### Code Quality

- **Seed path deduplication** (TD-017 closed)
  - `data_sources.py` now imports `DEFAULT_SEED_PATH` from `dataset_pipeline.py`
  - Eliminated duplicate path constant

### Testing

- **57 automated tests** (up from 37)
  - `SsrfRedirectTests` (4 tests) — redirect hook behavior
  - `UploadValidationTests` (5 tests) — size limit and MIME validation
  - `AnonymousSessionIsolationTests` (4 tests) — session key binding
  - `HealthCheckTests` (3 tests) — DB ping, version, status
  - `BlueprintSaveTests` (2 tests) — blueprint save/load round-trip
  - `UploadApiTests` (2 tests) — E2E upload with fixture CSV

### Documentation

- Updated `docs/SECURITY.md` — comprehensive security posture for v0.2.0
- Updated `docs/DEPLOYMENT.md` — rate limiting, health check, CI/CD sections
- Updated `docs/TECHNICAL_DEBT.md` — TD-003, TD-005, TD-006, TD-017, TD-019 closed
- Updated `README.md` — Phase 1.5 features, v0.2.0 status

---

## [0.1.0] — 2026-07-13 — Phase 1 Release Candidate

See `docs/PHASE1_RETROSPECTIVE.md` for full Phase 1 change log.

### Summary

- Modular analytics engine (KPI, chart, insights engines)
- Unified dataset pipeline (CSV + PostgreSQL sources)
- DRF serializers and service-oriented backend
- NVIDIA AI integration with local fallback
- Role-aware dashboard (CEO, Marketing Manager, Team Member)
- Session-based chat memory
- Dataset upload and URL ingestion
- Structured logging
- 31 automated tests
- Architecture documentation, ADR register, technical debt register
