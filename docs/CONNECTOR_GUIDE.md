# Universal Connector Developer Guide (v0.7.0)

This developer guide describes the architecture of the Universal Connector Framework and how to add new data source connectors to Nexa Analytics.

---

## 1. Directory Structure

All database connector actions are orchestrated in:
*   [connector_pipeline.py](file:///d:/.Study/pep%20class/Django/ai_assistant/analytics_assistant/connector_pipeline.py): Connection testing, table discovery, data queries, and synchronization flows.
*   [crypto.py](file:///d:/.Study/pep%20class/Django/ai_assistant/analytics_assistant/crypto.py): Reusable AES-256 password encryption module.
*   [models.py](file:///d:/.Study/pep%20class/Django/ai_assistant/analytics_assistant/models.py): Schema definitions for `DatasetUpload` metadata.

---

## 2. In-Memory Credential Cryptography

We use symmetric AES-256 (Fernet) encryption for sensitive database credentials. Passwords are encrypted before writing to `connection_config` and decrypted only in-memory:

```python
from .crypto import encrypt_password, decrypt_password

# 1. Encrypt before storing in JSONField
config = {
    "host": "localhost",
    "username": "postgres",
    "password": encrypt_password("plaintext_password"),
    "database": "sales_db",
}

# 2. Decrypt on-the-fly for database clients
password = decrypt_password(config.get("password", ""))
```

---

## 3. Developing a New Connector

To introduce a new database connector (e.g. MySQL, Snowflake):

### Step 3.1: Update Models
Extend `DatasetUpload.SOURCE_CHOICES` in [models.py](file:///d:/.Study/pep%20class/Django/ai_assistant/analytics_assistant/models.py) with the new type choice:
```python
SOURCE_CHOICES = (
    ("file", "File"),
    ("url", "URL"),
    ("postgres", "PostgreSQL"),
    ("mysql", "MySQL"), # New option
)
```

### Step 3.2: Implement Connector Client
Add connection, test, discovery, and query helper methods inside [connector_pipeline.py](file:///d:/.Study/pep%20class/Django/ai_assistant/analytics_assistant/connector_pipeline.py):
```python
def test_mysql_connection(config: dict) -> tuple[bool, str]:
    # 1. Decrypt password
    # 2. Connect via mysql client
    # 3. Return success tuple
    pass
```

### Step 3.3: Map Synchronization Hook
Extend `sync_dataset_source` in [connector_pipeline.py](file:///d:/.Study/pep%20class/Django/ai_assistant/analytics_assistant/connector_pipeline.py) to route to the new client query method when triggering refreshes:
```python
elif source_type == "mysql":
    # 1. Fetch MySQL DataFrame
    # 2. Save snapshot CSV
    # 3. Call persist_dataset_activation()
```

### Step 3.4: Register Routes and UI forms
1. Create frontend forms in `dashboard.html`'s `Connector Library` card.
2. Bind form submissions, tests, and listings inside `dashboard.js`'s `initConnectors()`.
