# Phase 8: Background Processing (Placeholder)

## Overview
- **Goal**: Offload heavy database sync tasks and AI generation jobs to background worker processes.
- **Problem being solved**: Fetching large databases or waiting for NVIDIA API timeouts blocks server responses, leading to request timeouts.
- **Why this phase existed**: Essential scaling roadmap step to support concurrent users without performance degradation.

---

## Features Added (Planned)
- Celery worker task integration.
- Redis broker state manager.
- Progress percentage bar on ingestion UI.

---

## Architecture Decisions
- **Asynchronous Sync**: Shift psycopg connections out of the HTTP view cycle into background jobs, updating state status fields asynchronously.

---

## Database Changes
### Models
- `IngestionJob` gains progress percentage and task UUID fields.

---

## Backend Changes
- **Modules**: Introduce `tasks.py` worker declarations.

---

## Frontend Changes
- **Progress Track**: Add polling state callbacks to progress bars in the UI.

---

## Security Improvements
- Limits concurrent requests per session key to protect resources.

---

## Testing
- Background mock task runner tests.

---

## Ponytail Review
- TBD.

---

## Lessons Learned
- TBD.

---

## Version Summary
- **Release**: `v0.8.0` (Planned)
- **Test count**: `99` tests (current baseline)
- **Major accomplishments**: Architecture draft for asynchronous tasks complete.
- **Known limitations**: TBD.
