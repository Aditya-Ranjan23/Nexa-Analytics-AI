# Product & Engineering Roadmap

This document outlines completed milestones, current active sprints, upcoming releases, and long-term architectural visions for Nexa Analytics AI.

---

## 1. Release Timeline Overview

```
                 [v0.1.0] Prototypes & AI Chat Validation
                    │
                 [v0.5.0] Stabilization sprint & thin service layers
                    │
                 [v0.6.0] Multi-dataset, Workspace Scoping, & Profiles
                    │
                 [v0.7.0] Prioritized Anomalies & Business Impact math
                    │
                 [v0.7.1] UI Polish, Loading Skeletons, Focus rings (CURRENT)
                    │
                    ▼
                 [v0.8.0] Async worker processing & Celery tasks (PLANNED)
```

---

## 2. Milestone Details

### Completed Milestones
- **Phase 0 — Foundation**: Simple CSV file parsing, basic Chart.js dashboards, and raw chatbot integrations.
- **Phase 1 — Stabilization**: Extracted view business logic into services and decomposed monolithic calculations into focused engines. Added 26 tests.
- **Phase 1.5 — Security**: Built DNS resolution guards against SSRF loop vectors and enforced environment config validation.
- **Phase 2 — Dataset Library**: Multiple file CRUD support, active/archived state filters, and cosmetic selectors cleanup.
- **Phase 2.1 — Version snapshotting**: Immutable history tables, statistical comparison engines, and instant rollbacks.
- **Phase 3 — Workspace isolation**: Containment shells grouping dashboard configurations and chat logs.
- **Phase 4 — Identity & Profiles**: Organizations tenant separations, invitation-scoped memberships, and profiles preference updates.
- **Phase 5 — Universal DB Connector**: PostgreSQL connection forms with Fernet credential encryption.
- **Phase 6 — Premium SPA Header**: Sticky headers, logo indicators, active workspace pills, and login modal overlays.
- **Phase 7 — Intelligent Analytics Engine**: Prioritized severity weights, chronological sub-segment analysis category drivers, and business impact math.
- **Phase 7.1 — Analytics Refinement**: Date de-duplication checks and flat trend contradiction filters.
- **Phase 7.2 — UI Spacing & Polish**: Spacing variables standardization, custom keyboard outlines, chart skeleton loading screens, and badge-rendered recommended action cards.

---

### Current Active Phase
- **Phase 7.2 — UI/UX Stabilization & Verification**: Finalizing documentation audits, resolving cross-link warnings, and certifying test suite green statuses.

---

### Upcoming Milestones (Planned)
- **Phase 8 — Background Task Processing**:
  - Integrate Celery worker tasks with Redis message brokers.
  - Offload psycopg connection sync runs and NVIDIA API fetches to async queues.
  - Implement dynamic sync progress status updates in client components.
- **Phase 9 — Multi-User Workspace Sharing**:
  - Support collaborative access to single workspace projects.
  - Design invite tokens workflow and team dashboards.

---

## 3. Deferred Technical Debt Roadmap

| Debt ID | Summary | Impact | Planned Resolution Sprint |
|---|---|---|---|
| **TD-019** | SSRF redirect chains | SSRF checks can be bypassed if outbound URLs redirect internally | Phase 8.1 Security |
| **TD-020** | Anonymous session isolation | Cookie-dependent sessions can leak if cookies expire or overlap | Phase 8.2 Identity |
| **TD-021** | In-memory psycopg reads | Large table query reads fetch rows in-memory, risking out-of-memory crashes | Phase 8 Ingestion |
| **TD-022** | API Rate Limiting | Open API summaries are vulnerable to DOS attempts | Phase 9 Deploy |
