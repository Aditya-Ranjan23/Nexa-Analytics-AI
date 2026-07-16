# Project History & Version Timeline

This document tracks the chronological evolution of Nexa Analytics AI from its initial foundation prototype to the current production-hardened release.

---

## Chronological Timeline

### 📅 July 01, 2026 — Version v0.1.0: Core Foundation Prototype
- **Milestone**: Core analytics engine prototype.
- **Architecture Evolution**:
  - Implemented Django shell project structure.
  - Set up a monolithic `views.py` handling file parsing, state, and completions.
  - Set up a monolithic `analytics.py` executing all statistical summaries.
- **Important Decisions**:
  - Leveraged single-file CSV/Excel upload with dual-write paths to `media/datasets/` and `data/sales_data.csv`.
- **Engineering Lessons**:
  - Dual data paths lead to file synchronization drift; code duplication in view actions blocks clean regression testing.

---

### 📅 July 13, 2026 — Version v0.5.0: Stabilization & Layer Refactoring
- **Milestone**: Modular decomposition sprint.
- **Architecture Evolution**:
  - Refactored `views.py` into thin controllers delegating to `upload_service.py` and `chat_service.py`.
  - Extracted shared HTTP request parameters handling to `request_context.py`.
  - Decomposed the `analytics.py` monolith into specialized engines: `kpi_engine.py`, `chart_engine.py`, `insights_engine.py`, and `column_utils.py`.
  - Created `dataset_pipeline.py` as a single load path.
- **Important Decisions**:
  - Introduced the first automated test suite (26 tests).
  - Switched from raw text error returns to standard DRF serializer fields.
- **Engineering Lessons**:
  - Separating data loading from calculation modules enables unit-testing engines without spinning up active database instances.

---

### 📅 July 14, 2026 — Version v0.5.5: Phase 1.5 Security Sprint
- **Milestone**: SSRF validation and startup hardening.
- **Architecture Evolution**:
  - Created `url_safety.py` containing hostname resolution checks.
  - Created validation checks inside `config/env_validation.py` to prevent insecure deployment credentials.
- **Important Decisions**:
  - Enforced server-side address resolution checking via `socket.getaddrinfo` to block SSRF attempts.
  - Configured hard startup exceptions if `DEBUG=True` under production environments.
- **Engineering Lessons**:
  - IP blocklists alone are vulnerable to DNS Rebinding; resolving domain addresses to resolved IPs is required.

---

### 📅 July 14, 2026 — Version v0.6.0: Dataset Library Catalog
- **Milestone**: Multi-dataset CRUD support.
- **Architecture Evolution**:
  - Extended standard database records with archive and rename parameters.
  - Implemented dynamic dataset activation filters scoped by user session keys.
- **Important Decisions**:
  - Removed the cosmetic non-functional role selector dropdown, matching code dependencies to save overhead.
- **Engineering Lessons**:
  - Deleting dead code (like placeholders) early reduces compiler clutter.

---

### 📅 July 14, 2026 — Version v0.6.1: Dataset Version snapshotting
- **Milestone**: Version rollback and statistical comparisons.
- **Architecture Evolution**:
  - Created the `DatasetVersion` model capturing snapshot records.
  - Designed schema comparison algorithms checking numeric distribution changes.
- **Important Decisions**:
  - Restoring previous versions swaps stored paths inside `DatasetUpload` dynamically.
- **Engineering Lessons**:
  - Decoupling version snapshot files from active files keeps query speeds constant.

---

### 📅 July 15, 2026 — Version v0.6.2: Workspace Foundation
- **Milestone**: Project project scope isolation.
- **Architecture Evolution**:
  - Created the `Workspace` model as the primary data container.
  - Enforced workspace FK references on dataset records.
- **Important Decisions**:
  - Backfilled historical datasets into auto-generated default workspaces for backward compatibility.
- **Engineering Lessons**:
  - Writing clean backfill migrations prevents test suite failure during structural updates.

---

### 📅 July 15, 2026 — Version v0.6.3: Organizations & Profiles
- **Milestone**: Team-level membership scopes.
- **Architecture Evolution**:
  - Created `Organization` and `OrganizationMember` models (roles: owner, admin, analyst, viewer).
  - Created `UserProfile` settings configuration mappings.
- **Important Decisions**:
  - Bound member permissions verification checkpoints to requests flow.
- **Engineering Lessons**:
  - Signal-driven post-save profile setups prevent null configuration loads.

---

### 📅 July 15, 2026 — Version v0.6.4: PostgreSQL Connector Ingestion
- **Milestone**: Universal database connector framework.
- **Architecture Evolution**:
  - Integrated `connection_config` parameter fields inside `DatasetUpload`.
  - Added symmetric decryption steps in-memory.
- **Important Decisions**:
  - Configured Fernet cryptographic password protection backed by `settings.SECRET_KEY`.
- **Engineering Lessons**:
  - Symmetric database connection configurations save users from duplicating models for custom schemas.

---

### 📅 July 15, 2026 — Version v0.6.5: Premium Layout & Modals
- **Milestone**: SaaS visual SPA dashboard shell.
- **Architecture Evolution**:
  - Integrated a sticky header, logo, active workspace selector, and settings mod.
  - Added AJAX-driven authentication dialog modal containers.
- **Important Decisions**:
  - Enforced fragment hash tracking (`#dashboard`) to save client-side routing reload latency.
- **Engineering Lessons**:
  - Single-page applications can preserve deep-linking using path location hashes.

---

### 📅 July 16, 2026 — Version v0.7.0: Intelligent Analytics Engine
- **Milestone**: Prioritized insights notification system.
- **Architecture Evolution**:
  - Integrated prioritized anomaly alerts inside `intelligent_analytics.py`.
  - Implemented category drivers analysis and business impact metrics.
- **Important Decisions**:
  - Resolved contradictions (e.g. daily volatility vs. flat trend lines) in-memory before rendering text summaries.
- **Engineering Lessons**:
  - Filtering data anomalies prior to LLM completions saves generation cost and reduces hallucination loops.

---

### 📅 July 16, 2026 — Version v0.7.1: UI Spacing & Polish (Current)
- **Milestone**: Premium SaaS spacing scale and loading screens.
- **Architecture Evolution**:
  - Defined variables for standard margins and card borders in `dashboard.css`.
  - Injected skeleton screens inside KPI panels and Chart.js canvases while fetches resolve.
- **Important Decisions**:
  - Replaced raw text lists with badge-coded recommended action cards.
- **Engineering Lessons**:
  - Polishing loading skeletons and custom keyboard outlines raises client trust and ensures AA accessibility.
