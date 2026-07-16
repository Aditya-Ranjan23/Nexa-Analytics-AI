# Phase 2: Versioning Retrospective

## Overview
- **Goal**: Implement dataset versioning to capture historical snapshots of dataset files, compare schemas/profiles, and roll back metrics state.
- **Problem being solved**: Updates to datasets overwrote previous records, making it impossible to review performance over time or recover from schema breakages.
- **Why this phase existed**: Retaining snapshots is critical for data auditing and historical change tracking in enterprise analytics.

---

## Features Added
- Dataset version control history tab.
- Snapshot comparison tool (schema differences, column diffs).
- Restore and rollback system to reset datasets to previous version snapshots.

---

## Architecture Decisions
- **Immutable Snapshot Model**: Created `DatasetVersion` model to store copies of files, row counts, and blueprints under specific version indexes.
- **Comparison Engine**: Built numerical column stats comparisons (mean, min, max, diffs) and structural column lists mapping.

---

## Database Changes
### Models
- `DatasetVersion`: Links to parent `DatasetUpload` using a ForeignKey, storing file snapshots, active blueprints, and insights cache.
- `DatasetUpload` gained:
  - `active_version_number`: IntegerField indicating current resolved version.

---

## Backend Changes
- **Modules**: Modified `views.py` and `upload_service.py` to support versions incrementation and rollback actions.
- **API Endpoints**:
  - GET `/api/data/datasets/<pk>/versions/`
  - POST `/api/data/datasets/<pk>/versions/compare/`
  - POST `/api/data/datasets/<pk>/versions/<v>/rollback/`

---

## Frontend Changes
- **Versions Modal**: Added a dialog displaying chronological list of snapshots.
- **Compare Layout**: Renders comparison panels mapping added/deleted fields and stats shifts.

---

## Security Improvements
- Version creation and rollbacks are fully scoped under owner-access policies.

---

## Testing
- Tests added covering version creation, structural schema comparison, and restore rollback functions.

---

## Ponytail Review
- **Dead Code Removed**: Replaced multiple ad-hoc comparisons with a unified pandas stats generation framework.

---

## Lessons Learned
- **What worked**: Decoupling the active version state from metadata let the application restore profiles in under 50ms.

---

## Version Summary
- **Release**: `v0.6.1`
- **Test count**: `54` tests
- **Major accomplishments**: Version snapshotting, rollback, and comparison functionality built.
- **Known limitations**: Multi-file inputs not supported.
