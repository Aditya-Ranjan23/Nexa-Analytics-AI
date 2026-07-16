# Phase 5: Connector Framework Retrospective

## Overview
- **Goal**: Implement a dynamic connector framework supporting database ingestion from PostgreSQL endpoints.
- **Problem being solved**: Ingesting datasets via files or URLs was manual. Business operations need to sync directly from operational databases.
- **Why this phase existed**: Providing direct database integrations converts Nexa from a file utility into an active business data platform.

---

## Features Added
- PostgreSQL table connector.
- Dynamic data schema drift validation check.
- AES-256 Symmetric encryption for connection passwords.
- Sync job logger and Ingestion API.

---

## Architecture Decisions
- **ADR-025: Encrypted JSON Parameters**: Credentials are saved inside the parent `DatasetUpload` using a `connection_config` JSONField. Passwords are encrypted in-memory using Fernet key derivation backed by `settings.SECRET_KEY`.
- **Dynamic psycopg Ingestion**: Data reads resolve dynamically via temporary engine cursors.

---

## Database Changes
### Models
- `DatasetUpload` gained:
  - `connection_config`: JSONField storing credentials.
  - `last_sync_at`: DateTimeField tracking synchronizations.

---

## Backend Changes
- **Modules**: Created `data_sources.py` connectors, `crypto.py` encryption utilities, and `connector_pipeline.py`.
- **API Endpoints**:
  - POST `/api/data/datasets/<pk>/sync/`
  - POST `/api/data/datasets/test-connection/`

---

## Frontend Changes
- **Connector Form**: Created a form grid allowing parameters mapping (host, username, database, table name, credentials).
- **Status Badges**: Added visual indicators warning users of schema differences on active database tables.

---

## Security Improvements
- Implemented symmetric encryption for stored database credentials.
- Added strict DNS validation checking on connection hostnames.

---

## Testing
- Tests added verifying test connections, Postgres ingest query building, and Fernet encryption/decryption keys.

---

## Ponytail Review
- **Complexity Removed**: Saved connector settings inside the existing `DatasetUpload` model instead of building a separate database layout.

---

## Lessons Learned
- **What worked**: Cryptographic protection kept database credentials fully shielded from raw administration exposure.

---

## Version Summary
- **Release**: `v0.6.4`
- **Test count**: `83` tests
- **Major accomplishments**: Universal connector logic completed, credential encryption implemented.
- **Known limitations**: No scheduling cron daemon (sync triggered manually).
