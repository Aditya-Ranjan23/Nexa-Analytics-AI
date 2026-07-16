# Phase 0: Foundation Retrospective

## Overview
- **Goal**: Build a functional prototype of Nexa Analytics with a single dataset upload capability, a dashboard displaying basic KPIs and charts, and an AI chat assistant.
- **Problem being solved**: Tabular analytics are traditionally static and require business users to write SQL/code or use heavy BI tools. Phase 0 aimed to validate that users could upload a file and instantly get key insights.
- **Why this phase existed**: To establish the core Django project structure and test basic AI generation loops using the NVIDIA API.

---

## Features Added
- CSV and Excel file upload.
- Automated mode detection (Ads vs. Generic).
- Basic KPI cards (Total Revenue, Average Order Value, Conversions) and Chart.js rendering (Trend, Channel breakdown).
- Context-aware chatbot utilizing NVIDIA NIM completions API with simple conversation memory.
- Diagnostic Ingestion API log endpoints.

---

## Architecture Decisions
- **Monolithic Views**: All HTTP request parsing, file parsing, business rules, and template bindings were in a single `views.py`.
- **Dual-Write Data Storage**: Files were stored in `media/datasets/` and simultaneously copied to `data/sales_data.csv`.
- **Monolithic Analytics Facade**: All mathematical operations, chart aggregations, and formatting rules lived in `analytics.py` (~820 lines).

---

## Database Changes
### Models
- `ChatSession`: Keyed by user or Django session key, stores context role/title.
- `ChatMessage`: Stores messages with `role` (user/assistant) and `content`.
- `DashboardState`: Tracks current active upload and blueprint overrides.
- `IngestionJob`: Diagnostic database sync logs tracker.

---

## Backend Changes
- **Modules**: `views.py`, `analytics.py`, `services.py`.
- **API Endpoints**:
  - GET `/` (SPA dashboard UI)
  - GET `/api/analytics/summary/`
  - POST `/api/chat/`
  - POST `/api/data/upload/`

---

## Frontend Changes
- **SPA UI**: Simple 4-tab dashboard panel structure (Dashboard, Upload, Insights, Ask AI) with basic styling and custom theme toggles.
- **JavaScript**: Direct inline event handlers, manual DOM reconstruction, and standard Chart.js canvases inside wrappers.

---

## Security Improvements
- Basic CSRF cookie verification.
- Simple path sanitization for file uploads.

---

## Testing
- No automated unit tests existed during this initial prototype phase.

---

## Ponytail Review
- **Complexity**: Monolithic file structures were accepted for speed, but created debt around dual-write file synchronization.
- **Simplifications**: Reused raw dictionary mappings for Chart.js variables directly rather than constructing models.

---

## Lessons Learned
- **What worked**: Fast validation of NVIDIA completions.
- **What didn't**: Dual-path write drift (files got out of sync between media and the sales_data seed file).

---

## Version Summary
- **Release**: `v0.1.0` (unreleased prototype)
- **Test count**: `0` tests
- **Major accomplishments**: Core SPA dashboard rendered, chatbot answered questions about datasets.
- **Known limitations**: High risk of data drift, no validation on uploads, susceptible to crash on malformed dates.
