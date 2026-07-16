# Nexa Analytics AI Assistant

**v0.7.0 Release** — Intelligent Analytics Engine + Premium SaaS UX

Nexa Analytics is a premium AI-powered Business Intelligence (BI) dashboard backed by Django, NVIDIA AI NIM, and a highly modular analytics engine. It automatically identifies anomalies, computes category drivers, and calculates business impact metrics, delivering interactive business analyst memo reports immediately upon dataset connection.

---

## 🚀 Key Features

### 📈 Intelligent Analytics Engine (v0.7.0)
- **Prioritized Anomalies**: Automatically identifies and prioritizes business metrics deviations using custom severity weights (`critical`, `high`, `medium`, `low`).
- **Category Drivers**: Isolates date spikes and drops down to specific channel components using Chronological Sub-Segment Analysis.
- **Business Impact Math**: Computes metrics coverage gap ratios, daily deviation variances, and shift magnitudes.
- **Narrative Coherence**: Resolves contradictory insights (e.g. flat daily trends vs. volatile metrics) in-memory before generating reports.

### 🗄️ Dataset & Version Control Library
- **Dataset Catalog**: Supports connection, activation, archiving, and deletion of multiple datasets.
- **Immutable Version History**: Snapshots dataset schemas, row counts, and blueprints under specific version number indexes.
- **Version Comparisons**: Automatically analyzes statistical distribution shifts and column changes between snapshots, and supports instant rollback restoring.

### 🔌 Universal Connector Framework
- **PostgreSQL Ingestion**: Syncs data tables directly to the ingestion pipeline.
- **Symmetric Encryption**: Protects credentials in-memory using AES-256 (Fernet) backed by a 32-byte key generated from `settings.SECRET_KEY`.

### 🛡️ Production Hardening & Security
- **SSRF Safety**: DNS-aware validation blocks requests to private/loopback RFC1918 subnets and resolves hostnames before fetching. Attaches hooks to intercept redirect loops.
- **Environment Checks**: Boot fails immediately under staging/production if default secrets or `DEBUG=True` are detected.
- **Rate Limiting**: DRF throttling classes protect endpoints against abuse.

---

## 🛠️ Quick Start

### 1. Install dependencies
Ensure you are using python 3.10+ and run:
```bash
pip install -r requirements.txt
```

### 2. Configure environment
Create a local config file:
```bash
cp .env.example .env
# Optional: Set NVIDIA_API_KEY from build.nvidia.com for AI summaries
```

### 3. Run migrations & start server
```bash
python manage.py migrate
python manage.py runserver
```
Open **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)** in your browser.

---

## 📋 REST API Summary

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/analytics/summary/` | Active dashboard statistics, prioritized anomalies, and KPI lists |
| `POST` | `/api/chat/` | Assistant chat with session-based memory lookup |
| `POST` | `/api/data/upload/` | Upload CSV/Excel files with schema profiling |
| `POST` | `/api/data/upload-link/` | Ingest datasets from secure HTTP links |
| `GET` | `/api/data/datasets/` | List datasets available inside the workspace |
| `POST` | `/api/data/connectors/test/` | Test connection credentials verification for database targets |
| `GET` | `/health/` | Health check endpoint returning database liveness (returns 503 on database drop) |

For complete payloads, request variables, and schema models, see the [API Reference Guide](docs/API_REFERENCE.md).

---

## 🧪 Running Tests

Verify code stability and security gates by running:
```bash
python manage.py test
# 99 tests (100% green)
```

---

## 📚 Documentation Index

The complete project documentation is located under `/docs`:

- 🏛️ **[System Architecture](docs/ARCHITECTURE.md)** — Core modules reference and ADR records.
- ⚙️ **[Technical Design](docs/SYSTEM_DESIGN.md)** — Request lifecycles, schemas, and Mermaid flowcharts.
- 🛡️ **[Security Control](docs/SECURITY.md)** — SSRF filters, encryption logic, and checklist.
- 🌐 **[Connectors Guide](docs/CONNECTOR_GUIDE.md)** — Guide for creating new connectors.
- 🕒 **[Version History](docs/PROJECT_HISTORY.md)** — Chronological release timeline log.
- 🗺️ **[Product Roadmap](docs/ROADMAP.md)** — Upcoming milestones and technical debt paydowns.
- 📋 **[Documentation Index](docs/README.md)** — Directory table pointing to phase retrospectives.
