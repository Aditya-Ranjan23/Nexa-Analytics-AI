# Testing Guide & Strategy

Nexa Analytics uses automated tests to guarantee system stability and verify security controls across all calculation engines and request contexts.

---

## 1. Testing Strategy

The test suite is structured to cover the following tiers:

```
                  ┌─────────────────────────────────┐
                  │      API Integration Tests      │
                  │   HTTP endpoints, Auth flow     │
                  └────────────────┬────────────────┘
                                   │
                  ┌────────────────▼────────────────┐
                  │        Security Tests           │
                  │   SSRF validation, Tenant, CSRF │
                  └────────────────┬────────────────┘
                                   │
                  ┌────────────────▼────────────────┐
                  │       Unit/Calculations         │
                  │   Anomalies, Diffs, Blueprints  │
                  └─────────────────────────────────┘
```

- **In-Memory database runs**: Uses SQLite in-memory databases during tests to execute checks in under 50ms per test.
- **Hermetic executions**: Outbound HTTP checks (like NVIDIA API fetches and URL imports) are mocked or safely stubbed during tests to prevent external network calls.

---

## 2. Test Suites by Module

All test cases are declared in `analytics_assistant/tests.py`, divided into functional categories:

### Unit Tests
- **`SchemaTests`**: Verifies dynamic date, key identifiers, and column mode validations.
- **`RoleTests`**: Confirms normalization of widgets mapping context.
- **`AnalyticsEngineTests`**: Assesses standard deviations boundaries, empty time-series fallbacks, and statistical profiling.
- **`DatasetPipelineTests`**: Verifies file resolution paths, database connectors schema fallbacks, and fallback seed files loading.

### Integration Tests
- **`ApiIntegrationTests`**: Simulates HTTP client requests targeting summary endpoints, blueprint overrides, chat configurations, and connector credentials sync queries.
- **`DatasetComparisonTests`**: Validates pandas statistics shift calculation and added/removed columns output formats.
- **`DatasetVersioningTests`**: Validates sequential version increments, snapshots storage, and active properties rollback functions.

### Security Tests
- **`UrlSafetyTests`**: Evaluates SSRF loop vectors, loopback IPs blocking, private RFC1918 blocklists, and hostname DNS resolution validation.
- **`WorkspaceIsolationTests`**: Assures that users cannot see or modify datasets belonging to different workspaces.
- **`ChatSessionScopeTests`**: Verifies that anonymous and authenticated chat requests cannot load session keys belonging to other user IDs.
- **`ContradictionResolutionTests`**: Verifies that anomalies de-duplication checks and flat trend filters resolve dates collision correctly.

---

## 3. How to Run Verification Scripts

### Run Entire Suite
Execute from the repository root:
```bash
python manage.py test
```

### Run Specific Test Class
To verify a single module:
```bash
python manage.py test analytics_assistant.tests.UrlSafetyTests
```

### Run Individual Test Case
To target a single scenario:
```bash
python manage.py test analytics_assistant.tests.ContradictionResolutionTests.test_contradiction_resolution
```

---

## 4. Test Coverage Statistics

| Core Module | Estimated Coverage | Regression Target |
|---|---|---|
| `intelligent_analytics.py` | ~92% | Anomaly severity sorting, drivers mapping, contradiction filters |
| `url_safety.py` | ~100% | SSRF host loops, DNS resolutions check |
| `request_context.py` | ~88% | Workspace containment scoping, session ownership checks |
| `dataset_pipeline.py` | ~95% | Single load path fallback, DB credentials resolution |
| `kpi_engine.py` | ~90% | Value formats normalization and metric selection |
| `views.py` | ~85% | API JSON parameters serialization validation |
