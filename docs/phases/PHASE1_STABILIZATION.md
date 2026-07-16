# Phase 1: Stabilization Retrospective

## Overview
- **Goal**: Harden the core codebase of the Nexa prototype without adding any frontend/backend features.
- **Problem being solved**: The codebase had a monolithic architecture with no test coverage, silent crashes on empty time series, and dual-path file storage drift.
- **Why this phase existed**: To establish architectural stability, structured logging, thin controllers, and modular analytics engines so the project could support new features safely.

---

## Features Added
- None. (Strict feature-freeze stabilization sprint).

---

## Architecture Decisions
- **ADR-008: Thin Views**: Extracted upload and chat logic into `upload_service.py` and `chat_service.py`, moving request resolution to `request_context.py`.
- **ADR-015: Decompose Analytics Monolith**: Split the 820-line `analytics.py` monolith into isolated engines: `kpi_engine.py`, `chart_engine.py`, `insights_engine.py`, and `column_utils.py`.
- **ADR-016: Unified Dataset Pipeline**: Set up a single source-of-truth loading path in `dataset_pipeline.py`. Deleted the dual-write to `data/sales_data.csv`.

---

## Database Changes
- None (Preserved existing models).

---

## Backend Changes
- **Modules**: Created `upload_service.py`, `chat_service.py`, `request_context.py`, `column_utils.py`, `kpi_engine.py`, `chart_engine.py`, `insights_engine.py`, `dataset_pipeline.py`.
- **API Endpoints**: Unchanged. Structured Django validation error messages via DRF serializers.

---

## Frontend Changes
- Unchanged. Retained the legacy 4-tab SPA interface.

---

## Security Improvements
- Chat session ownership checks implemented to prevent users from querying other users' chat IDs.
- Regex validation on environment-configured PostgreSQL table inputs.
- Sanitized file upload errors sent to the client (exposing generic user-safe summaries, stack traces only logged server-side).

---

## Testing
- Created a suite of 26 tests (`tests.py`) covering schema boundaries, role filtering context, and file loading pipelines.

---

## Ponytail Review
- **Complexity Removed**: Net code reduction and isolation of business logic from HTTP handlers.
- **Dead Code Removed**: Deleted legacy helper loops in `views.py`.
- **Modules Merged**: Unified double file-paths into a single path resolution logic.

---

## Lessons Learned
- **What worked**: Decoupling HTTP views from data validation helped pinpoint regression causes instantly.
- **What didn't**: Anonymous session isolation was deferred, remaining a known risk.

---

## Version Summary
- **Release**: `v0.5.0` (internal RC)
- **Test count**: `26` tests
- **Major accomplishments**: Stabilized monoliths, created the automated test suite, resolved dual-write drift.
- **Known limitations**: SSRF protection did not handle HTTP redirects.
