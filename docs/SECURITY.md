# Security & Hardening (v0.7.0)

This document details the security model, vulnerability mitigation controls, data isolation architectures, and compliance criteria enforced by Nexa Analytics AI.

---

## 1. URL Ingestion & SSRF Mitigation

Outbound HTTP queries submitted via `/api/data/upload-link/` present Server-Side Request Forgery (SSRF) risks. We block SSRF via a multi-layered validation module in `analytics_assistant/url_safety.py`:

| Validation Step | Rule Enforced |
|---|---|
| **Protocol Scheme** | Rejects non-HTTP / non-HTTPS schemas. |
| **Credentials Protection** | Rejects inline authentication structures (e.g. `user:pass@hostname`). |
| **Hostname Blocklist** | Prevents lookup of loopback addresses (`localhost`, `127.*`), local networks (`*.local`, `*.internal`), and cloud metadata services (`169.254.169.254`). |
| **IP Literal Checks** | Blocks direct IP literal URLs mapping to private or reserved subnets (RFC1918, RFC6598, multicast). |
| **DNS Resolution Gate** | Resolves domain mappings using `socket.getaddrinfo` *prior* to query execution. The request is aborted if any resolved target IP address maps to an internal subnet. |
| **Redirect Hook** | Implements custom redirection intercepts using `build_safe_session()` redirect hooks. Every redirection hop is re-validated against the DNS check before following links. |

---

## 2. Cryptographic Credential Protection

External database connection credentials stored inside `DatasetUpload.connection_config` are encrypted to prevent unauthorized administration visibility:
- **Encryption Algorithm**: Symmetrical AES-128/256 (Fernet) backed by a 32-byte key generated from `settings.SECRET_KEY`.
- **In-Memory Decryption**: Decryption of database passwords is performed strictly in-memory during sync or test connection flows. Raw passwords are never returned in serialization outputs.

---

## 3. Upload & File Hardening

Tabular file ingestion via `/api/data/upload/` enforces:
- **Format Verification**: Rejects files not matching `.csv`, `.xlsx`, or `.xls` suffix extensions.
- **Upload Size Limits**: Configures file limits using `MAX_UPLOAD_MB` (default 25MB), linked directly to Django's parsing buffer threshold `DATA_UPLOAD_MAX_MEMORY_SIZE`.
- **MIME Validation**: Validates file types after buffering to reject fake format tricks.

---

## 4. Rate Limiting & Throttling

All API routes are protected using Django REST Framework's throttling rules. Throttling is segmented by user authentication status:

| API Target Scope | Anonymous Limit | Authenticated Limit |
|---|---|---|
| **Global APIs** | 60 requests / minute | 120 requests / minute |
| **Chat Assistant** | 20 requests / minute | 40 requests / minute |
| **Dataset Uploads** | 10 requests / minute | 20 requests / minute |

Throttling levels are configurable via `.env` parameter overrides (e.g., `THROTTLE_ANON_RATE`).

---

## 5. Session & Data Isolation

- **Workspace Boundaries**: All database tables (`DatasetUpload`, `DashboardState`, `ChatSession`) belong to a `Workspace` ForeignKey. Owner validations are resolved at request context initialization.
- **Chat Log Protections**: Accessing chat memory tables enforces user ownership checks, preventing cross-user request leaks.
- **Anonymous Sessions**: Guest chat interactions bind strictly to Django `session_key` references, expiring alongside cookies.
