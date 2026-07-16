# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### [0.7.0] — 2026-07-15 — Phase 7: Intelligent Analytics Engine

### Added
- **Intelligent Analytics Engine**: Created advanced proactive calculations in `intelligent_analytics.py` for autonomous data analysis.
- **Statistical Anomaly Detection**: Implementation of non-ML statistical checks for missing values, duplicates, outliers (Z-score > 2.5), spikes/drops (sequential change > 25%), flat trends (change within 2%), category distribution shifts (value share change > 15%), and version-to-version schema changes.
- **Severity Ranking & Impact Scoring**: Integrated anomaly severity mapping (`critical`/`high`/`medium`/`low`) and quantitative business impact calculation (variance shift, coverage gaps, record count inflation).
- **Chronological Drivers & Explainability**: Added context-aware sub-segment analysis to automatically isolate the categories driving day-to-day spikes and drops.
- **Contradiction Resolution**: Implemented automatic conflict resolution (e.g. merging flat trends and daily spikes/drops into volatility highlights and de-duplicating double-spikes).
- **Trend Intelligence**: Added increase/decrease listings for all numeric fields, fastest growing and largest declining categories, day-of-week and monthly seasonality indicators, trend reversals, and growth acceleration/deceleration.
- **Root Cause & Attribution**: Implemented Net KPI shift contribution analysis grouping by category to track drivers of change.
- **Facts, Recommendations, & Speculations**: Formatted all heuristics recommendations into clearly demarcated "Fact: [...] Recommendation: [...] Speculation: [...]" blocks.
- **Dynamic Suggested Questions**: Added dynamic column/metric-aware question prompts.
- **Narrative Fallback Briefings**: Structured standard narrative briefing block (Executive, Management, Operational, Risk, Opportunity) with premium paragraph flow.
- **Glassmorphic UI Presentation**: Upgraded `dashboard.js` render loops to display severity badges, explainability drivers, and yellow business impact markers.
- **Integration Tests**: Added 6 verification test methods including `test_contradiction_resolution` and severity-sorting checks.

---

### [0.6.0] — 2026-07-15 — Universal Connector Framework & Premium Navigation

### Added
- **PostgreSQL Connection**: Support connection testing, schema discovery (table listing), and direct database table data pulling.
- **Credential Cryptography**: Implemented AES-256 Fernet password encryption backed by `settings.SECRET_KEY` inside `crypto.py`.
- **Dataset Sync & Versioning**: Replaced static sync logic with dynamic, source-aware sync that creates fresh `DatasetVersion` snapshots and detects column schema modifications.
- **Connector Library UI**: Unified tabbed ingestion UI containing CSV/Excel, PostgreSQL forms, and disabled "Coming Soon" cloud connection slots (Snowflake, BigQuery).
- **Connector API endpoints**: Mapped `/api/data/connectors/test/`, `/api/data/connectors/schema/`, `/api/data/connectors/ingest/`, and `/api/data/datasets/<id>/sync/` controllers.
- **SaaS Header**: Sticky top navigation bar containing logo, workspace context pill, user initials avatar, and core navigation menu.
- **Glassmorphic Auth Modal**: A single unified authentication modal on the dashboard for AJAX login and signup workflows, including remember me toggles and password visibility handlers.
- **SaaS Hero Section**: Customer-centric hero layout showing active dataset summary metrics with real-time green pulsing badges and last sync times.
- **Tests**: Appended `CryptographyTests`, `ConnectorPipelineTests`, and `AjaxAuthenticationTests` classes covering discovery, encryption, version incrementing, and AJAX auth flows.

---

### [0.5.0] — 2026-07-14 — Phase 4: Identity & User Experience

### Added
- **Authentication**: User registration, login with Remember Me (2 weeks cookie life), logout, and password reset form flows.
- **User Profile**: Extension `UserProfile` model containing display name, bio, timezone, avatar image, and theme preference.
- **Account Operations**: API views for updating profile details, saving preferences, exporting account JSON data, and deleting accounts.
- **Onboarding checklist**: Dashboard banner rendering step-by-step guidance for empty workspaces.
- **Dynamic Navigation**: Dynamic authentication-aware tabs (Profile/Settings/Logout vs Login/Register).

---

### [0.4.0] — 2026-07-14 — Phase 3: Workspace Foundation

### Added
- **Workspace Model**: Introduced `Workspace` to logically partition data ownership for authenticated users.
- **Backfill Migration**: Created Django schema and data migration to automatically allocate default workspaces to existing users and transition their datasets, dashboard states, and chat sessions.
- **Active Workspace Resolver**: Implemented `resolve_active_workspace()` helper in `request_context.py` to handle lookup and dynamic lazy-creation of workspace contexts.
- **Workspace Scoping**: Updated request context filters and chat orchestration to isolate listings, upload actions, and chat sessions by workspace.
- **Tests**: Appended `WorkspaceTests` class to [tests.py](file:///d:/.Study/pep%20class/Django/ai_assistant/analytics_assistant/tests.py) covering auto-creation, isolation checks, and anonymous user session preservation.

---

## [0.3.1] — 2026-07-14 — Pre-Phase 3 Audit

### Removed
- **Legacy Role Selector**: Deleted the legacy cosmetic role selector, style selectors, API paths, roles module, and associated tests to prepare for Phase 3 RBAC.

---

### Added
- **Dataset Versioning & History**:
  - Introduced `DatasetVersion` model to maintain chronological snapshots of dataset files, row counts, and blueprints.
  - Active version tracking on parent `DatasetUpload` through `active_version_number`.
  - Versions listing endpoint (`api/data/datasets/<pk>/versions/`).
  - Upload version file endpoint (`api/data/datasets/<pk>/versions/upload/`).
  - Ingest URL version endpoint (`api/data/datasets/<pk>/versions/url/`).
  - Restore version endpoint (`api/data/datasets/<pk>/versions/<number>/restore/`) which shifts the parent dataset to use a historic snapshot.
  - Compare versions endpoint (`api/data/datasets/<pk>/versions/compare/?v1=X&v2=Y`) which calculates row diffs, column schema modifications, and statistical profiling comparisons (means, ranges, and diffs) for common numeric columns.
  - Frontend Version History modal featuring inline file uploads, URL ingestion, restore buttons, and interactive checkbox comparison.
  - 6 new automated tests verifying the versioning listing, uploading, restoring, and statistical comparison.

### Fixed
- **Health Check Database Checks**: Restored the database cursors pinging mechanism on `/health/` to guarantee deep readiness checking.

### Changed
- Bumped health check API version response to `0.3.0`.

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
