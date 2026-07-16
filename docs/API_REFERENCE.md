# REST API Reference

This reference documents the REST API endpoints provided by the Nexa Analytics engine. All payloads and responses are formatted as JSON unless specified otherwise.

---

## 1. Authentication & Headers

Requests targeting protected endpoints must include:
- **CSRF Token Header**: `X-CSRFToken` cookie validation on all POST/PATCH/DELETE endpoints.
- **Session Authentication**: Active Django browser session cookies.

---

## 2. Analytics & Blueprint Endpoints

### GET `/api/analytics/summary/`
Fetch the complete summary payload for the active workspace dataset.

- **Request Headers**:
  - `Accept: application/json`
- **Response Status Codes**:
  - `200 OK` — Success.
- **Response Body**:
  ```json
  {
    "dataset_name": "Q2 Sales Invoices",
    "dataset_version": 2,
    "records": 4820,
    "columns": ["date", "channel", "revenue", "orders"],
    "dataset_mode": "ads",
    "last_sync_at": "2026-07-16T10:14:15Z",
    "kpis": {
      "total_revenue": 1420500,
      "total_orders": 8200
    },
    "charts": [
      {
        "title": "Revenue Performance",
        "type": "line",
        "data": [{"date": "2026-06-01", "revenue": 12000}]
      }
    ],
    "proactive_insights": {
      "top_kpis": [
        {"metric": "total_revenue", "total": 1420500, "average": 45000, "format": "currency"}
      ],
      "anomalies": [
        {
          "date": "2026-06-15",
          "metric": "revenue",
          "severity": "critical",
          "impact_score": 88.5,
          "driver_category": "Google Ads",
          "explanation": "Revenue spike driven by Q2 summer campaign discounts."
        }
      ]
    }
  }
  ```

---

### GET `/api/dashboard/blueprint/`
Fetch the active AI blueprint specification.

- **Response Body**:
  ```json
  {
    "effective_blueprint": {
      "x_axis": "date",
      "metrics": ["revenue", "orders"]
    }
  }
  ```

### POST `/api/dashboard/blueprint/`
Override the blueprint rules layout.

- **Request Body**:
  ```json
  {
    "blueprint": {
      "x_axis": "date",
      "metrics": ["revenue"]
    }
  }
  ```
- **Response Body**:
  ```json
  {
    "detail": "Blueprint saved. Dashboard will refresh."
  }
  ```

---

## 3. Dataset Management Endpoints

### GET `/api/data/datasets/`
List all datasets inside the active workspace container scope.

- **Response Body**:
  ```json
  [
    {
      "id": 1,
      "name": "Q2 Sales Invoices",
      "display_name": "Q2 Sales Invoices",
      "row_count": 4820,
      "source_type": "file",
      "is_active": true,
      "is_archived": false,
      "created_at": "2026-07-15T09:20:00Z"
    }
  ]
  ```

---

### POST `/api/data/upload/`
Upload a tabular file (CSV/Excel) to create a new dataset.

- **Request Content-Type**: `multipart/form-data`
- **Request Body**:
  - `file`: Tabular source file.
- **Response Body**:
  ```json
  {
    "detail": "Dataset activated successfully.",
    "rows": 4820,
    "dataset_mode": "generic"
  }
  ```

---

### POST `/api/data/upload-link/`
Ingest a dataset file from a public URL endpoint.

- **Request Body**:
  ```json
  {
    "url": "https://public.data.example.com/invoices.csv"
  }
  ```
- **Response Body**:
  ```json
  {
    "detail": "URL ingested successfully.",
    "rows": 1205,
    "dataset_mode": "generic"
  }
  ```
- **Error Responses**:
  - `400 Bad Request` — URL rejected due to SSRF safety limits:
    ```json
    {
      "detail": "URL rejected: Loops and private IPs blocked."
    }
    ```

---

### PATCH `/api/data/datasets/<id>/`
Rename or update dataset parameters.

- **Request Body**:
  ```json
  {
    "name": "Updated Dataset Name"
  }
  ```
- **Response Body**:
  ```json
  {
    "id": 1,
    "name": "Updated Dataset Name"
  }
  ```

---

### DELETE `/api/data/datasets/<id>/`
Delete a dataset and its versions permanently.

- **Response Status Codes**:
  - `204 No Content`
  - `404 Not Found`

---

### POST `/api/data/datasets/<id>/activate/`
Activate the dataset on the dashboard layout.

- **Response Body**:
  ```json
  {
    "detail": "Dataset activated successfully."
  }
  ```

---

### POST `/api/data/datasets/<id>/archive/`
Archive/unarchive the dataset.

- **Response Body**:
  ```json
  {
    "detail": "Dataset archived."
  }
  ```

---

## 4. Version Control Endpoints

### GET `/api/data/datasets/<id>/versions/`
List the version control snapshot logs for the parent dataset.

- **Response Body**:
  ```json
  [
    {
      "version_number": 2,
      "row_count": 4820,
      "created_at": "2026-07-16T10:14:15Z"
    },
    {
      "version_number": 1,
      "row_count": 4120,
      "created_at": "2026-07-15T09:20:00Z"
    }
  ]
  ```

---

### POST `/api/data/datasets/<id>/versions/compare/`
Compare schema structure and statistics between two versions.

- **Request Body**:
  ```json
  {
    "version_a": 1,
    "version_b": 2
  }
  ```
- **Response Body**:
  ```json
  {
    "schema_changes": {
      "added_columns": ["conversion_rate"],
      "removed_columns": []
    },
    "profile_changes": {
      "revenue": {
        "mean_diff": 450.5,
        "max_diff": 12000
      }
    }
  }
  ```

---

### POST `/api/data/datasets/<id>/versions/<v>/rollback/`
Rollback active properties of the parent dataset to the target snapshot version code.

- **Response Body**:
  ```json
  {
    "detail": "Dataset rolled back to version 1 successfully."
  }
  ```

---

## 5. External Database Connector Endpoints

### POST `/api/data/datasets/test-connection/`
Test credentials connection properties for database servers.

- **Request Body**:
  ```json
  {
    "host": "localhost",
    "port": 5432,
    "database": "sales_db",
    "user": "postgres",
    "password": "secretpassword",
    "table_name": "revenue_summary"
  }
  ```
- **Response Body**:
  ```json
  {
    "detail": "Database connection verified successfully."
  }
  ```

---

### POST `/api/data/datasets/<id>/sync/`
Connect to the database sync targets, fetch updates, increment version, and sync metrics.

- **Response Body**:
  ```json
  {
    "detail": "Sync complete.",
    "version_number": 3,
    "rows": 4890,
    "schema_changed": false
  }
  ```

---

## 6. AI Conversational Assistant Endpoints

### POST `/api/chat/`
Submit messages to the context conversational assistant.

- **Request Body**:
  ```json
  {
    "message": "Why did conversions spike on June 15?",
    "session_id": "active-session-key-uuid-or-empty"
  }
  ```
- **Response Body**:
  ```json
  {
    "reply": "Conversions spiked 24% on June 15 due to Google Ads summer discounts.",
    "session_id": "active-session-key-uuid",
    "powered_by_nvidia": true
  }
  ```
