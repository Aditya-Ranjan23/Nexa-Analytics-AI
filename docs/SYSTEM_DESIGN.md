# System Design & Architecture

This document describes the core technical architecture, design patterns, lifecycle flows, pipelines, and schema mappings of Nexa Analytics AI.

---

## 1. Overall System Architecture

Nexa Analytics is organized around a classic clean layered architecture:

```
                  ┌──────────────────────────────┐
                  │       Client (Browser)       │
                  │ HTML · JavaScript · CSS · JS │
                  └──────────────┬───────────────┘
                                 │ HTTP / REST
                  ┌──────────────▼───────────────┐
                  │     Django View Layer        │
                  │ Thin controllers, Serializer │
                  └──────────────┬───────────────┘
                                 │
                  ┌──────────────▼───────────────┐
                  │        Service Layer         │
                  │ Ingestion, Chat, Encrypt API │
                  └──────────────┬───────────────┘
                                 │
                  ┌──────────────▼───────────────┐
                  │    Analytics/Engine Layer    │
                  │ KPI, Charts, Intelligent, PD │
                  └──────────────┬───────────────┘
                                 │
                  ┌──────────────▼───────────────┐
                  │          Data Layer          │
                  │ DatasetPipeline, SQL, Fernet │
                  └──────────────────────────────┘
```

---

## 2. Request Lifecycle

The following sequence details how client API requests resolve:

```mermaid
sequenceDiagram
    autonumber
    actor User as Client Browser
    participant Django as Django Middleware
    participant View as views.py (Controller)
    participant ReqCtx as request_context.py
    participant Service as Ingestion/Chat Service
    participant Engine as Analytics Engine
    participant DB as SQLite / postgres

    User->>Django: GET /api/analytics/summary/ (headers, cookies)
    Django->>Django: CSRF token check & Auth validation
    Django->>View: Dispatch validated request
    View->>ReqCtx: resolve_dashboard_state(request)
    ReqCtx->>DB: Query Active Workspace & DatasetUpload
    DB-->>ReqCtx: Return instances
    ReqCtx-->>View: Active active_upload & workspace
    View->>Engine: build_analytics_payload(active_upload)
    Engine->>Engine: Process pandas stats & anomalies
    Engine-->>View: JSON serializable data payload
    View-->>User: HTTP 200 OK (Clean JSON response)
```

---

## 3. Dataset & Version Lifecycles

### Dataset Lifecycle States
Datasets transit through various states based on ingestion status and user interactions:

```mermaid
stateDiagram-RTL
    [*] --> Uploaded: User uploads File/URL
    Uploaded --> Processing: Ingestion starts
    Processing --> Processed: Validation green
    Processing --> Failed: Schema errors or SSRF block
    Processed --> Active: User selects/activates dataset
    Processed --> Archived: User clicks Archive
    Archived --> Processed: Unarchive toggle
    Processed --> Deleted: User deletes dataset
    Deleted --> [*]
```

### Dataset Version snapshotting
Versions are captured sequentially under the parent file header:

```mermaid
graph TD
    Upload[DatasetUpload: Base Record]
    V1[DatasetVersion: v1 Snapshot]
    V2[DatasetVersion: v2 Snapshot]
    V3[DatasetVersion: v3 Snapshot]

    Upload -->|Has Many| V1
    Upload -->|Has Many| V2
    Upload -->|Has Many| V3

    style V3 fill:#8b5cf6,stroke:#fff,stroke-width:2px,color:#fff
```
- **Incremental Bumps**: Uploading a new file to an existing dataset increments the version number index, snapshots the old path to a `DatasetVersion` entry, and overwrites the parent properties with the new payload.
- **Rollback Transitions**: Rolling back to version `v1` copies the blueprint and file attributes from the `v1` version record back to the parent `DatasetUpload` record.

---

## 4. Universal Connector Ingestion Flow

Connectors sync external endpoints to the local storage pipeline:

```mermaid
graph TD
    Form[User enters connection parameters] --> Test[Test Connection API]
    Test -->|psycopg validation| Save[Save DatasetUpload connection_config]
    Save -->|Encrypt password| Crypto[Fernet Encrypted fields]
    Save --> Sync[Execute Sync Job]
    Sync --> Connect[Connect to Postgres endpoint]
    Connect --> Query[Fetch daily/hourly table snapshot]
    Query --> SchemaCheck[Compare schema columns with v-previous]
    SchemaCheck -->|Schema changes| Warning[Flag Schema Drift warning badge]
    SchemaCheck --> SaveFile[Write snapshot file to media/datasets/]
    SaveFile --> Bump[Increment version and activate]
```

---

## 5. Intelligent Analytics Pipeline

Surfaces prioritized insights using deterministic math combined with generative summarizations:

```mermaid
flowchart TD
    Raw[Raw Ingested Pandas DataFrame] --> Profile[Run standard deviations & stats calculations]
    Profile --> Anomaly[Identify spike & drop date points]
    Anomaly --> Severity[Calculate severity weights: critical, high, medium, low]
    Severity --> Contradiction[Filter Trend conflicts - Volatility vs. Flat lines]
    Contradiction --> Deduplicate[De-duplicate anomaly entries on identical calendar dates]
    Deduplicate --> Prompt[Construct prioritized context prompt]
    Prompt --> NIM[Submit prompt context to NVIDIA NIM API]
    NIM --> Format[Parse response text into clean business analyst memo]
    Format --> Client[Render recommendation grid cards to User Dashboard]
```

---

## 6. Database Schema Overview

| Model | Primary Purpose | Key Fields | Relationships |
|---|---|---|---|
| **Organization** | Tenant boundary | `name`, `slug`, `settings_json` | Parent to members |
| **OrganizationMember** | User organization access role | `role` (owner/admin/analyst/viewer) | FK to User, FK to Organization |
| **Workspace** | Project workspace isolate shell | `name` | FK to owner User |
| **DatasetUpload** | Primary dataset asset | `stored_path`, `connection_config`, `active_version_number`, `insights_cache` | FK to Workspace, FK to Organization |
| **DatasetVersion** | Version snapshot | `stored_path`, `row_count`, `ai_blueprint`, `insights_cache` | FK to DatasetUpload |
| **DashboardState** | Client view persistence | `blueprint_override` | FK to DatasetUpload, FK to User |
| **UserProfile** | User parameters customization | `display_name`, `avatar`, `bio`, `timezone`, `theme_preference` | OneToOne to User |

---

## 7. Caching Strategy

- **Insights Caching**: Analytics payloads, anomalies, and AI summaries are cached inside the `insights_cache` field of `DatasetUpload` and `DatasetVersion`.
- **Cache Evacuation**: Resetting blueprints, running manual synchronizations, or rolling back versions invalidates the cache immediately, triggering a recalculation cycle on the next payload summary request.

---

## 8. Deployment & Security Architecture

### Security Controls
- **SSRF Mitigation**: Hostnames resolved via `socket.getaddrinfo` are checked against loopback, multicast, private RFC1918, and carrier-grade NAT address lists.
- **Symmetric Encryption**: Connection passwords are encrypted in-memory using Fernet key derivation backed by `settings.SECRET_KEY`.
- **Environment Safety**: Application boot throws a hard exception if `DJANGO_ENV` is set to `production` or `staging` while `DEBUG=True`.
