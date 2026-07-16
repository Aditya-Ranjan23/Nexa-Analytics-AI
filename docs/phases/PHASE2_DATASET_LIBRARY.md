# Phase 2: Dataset Library Retrospective

## Overview
- **Goal**: Implement a dataset library where users can upload and manage multiple datasets, activate them dynamically, rename, archive, or delete them.
- **Problem being solved**: The original dashboard supported only one active dataset at a time, overwriting previous uploads.
- **Why this phase existed**: A structured dataset catalog is critical for any multi-tenant analytics tool to let users pivot between different metrics.

---

## Features Added
- Dataset Library list tab.
- Activate, archive/unarchive, rename, and delete actions on dataset items.
- Dataset details metadata parsing (row count, source type, timestamp).

---

## Architecture Decisions
- **ADR-020: Centralized dataset ownership**: Created a shared request context filter `user_dataset_queryset(request)` to scope active user files.
- **ADR-021: Block archived dataset activation**: Blocked dashboard states from activating archived datasets to keep metrics states clean.
- **ADR-023: Clean up Cosmetic Role Selector**: Deleted legacy non-functional selector, files, and rules.

---

## Database Changes
### Models
- `DatasetUpload` gained:
  - `name`: CharField for dataset labelling.
  - `description`: TextField.
  - `is_archived`: BooleanField.

---

## Backend Changes
- **Modules**: Modified `views.py` to support GET/POST/PATCH/DELETE on `/api/data/datasets/`.
- **API Endpoints**:
  - GET/POST `/api/data/datasets/`
  - PATCH/DELETE `/api/data/datasets/<pk>/`
  - POST `/api/data/datasets/<pk>/activate/`
  - POST `/api/data/datasets/<pk>/archive/`

---

## Frontend Changes
- **Data Tab**: Added a clean layout listing all uploaded datasets in cards with action triggers.
- **Dynamic Activation**: Clicking activate triggers AJAX fetch to update dashboard states in real-time.

---

## Security Improvements
- Isolated active datasets by authenticated user session. Anonymous user files are scoped to session keys.

---

## Testing
- Added tests verifying archive boundaries, delete safeguards, and ownership filters.

---

## Ponytail Review
- **Complexity Removed**: Deleting the cosmetic role selector simplified client-server APIs.
- **Simplifications**: Consolidated multiple database detail queries into one optimized query helper.

---

## Lessons Learned
- **What worked**: Shared dataset querying context stopped accidental leaking of data files between sessions.

---

## Version Summary
- **Release**: `v0.6.0`
- **Test count**: `42` tests
- **Major accomplishments**: Multi-dataset catalog and CRUD completed, legacy role selectors cleaned up.
- **Known limitations**: No version history tracking for a single dataset.
