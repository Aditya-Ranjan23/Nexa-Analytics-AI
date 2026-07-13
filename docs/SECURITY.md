# Security Notes — Nexa Analytics v0.2.0 (Phase 1.5)

## URL Ingestion (SSRF) — Fully Hardened

`/api/data/upload-link/` fetches remote URLs server-side. Guards in `analytics_assistant/url_safety.py`:

| Layer | Check |
|-------|--------|
| Scheme | `http` / `https` only |
| Credentials | Rejects `user:pass@host` URLs |
| Hostname blocklist | `localhost`, `*.local`, `*.internal`, cloud metadata host |
| IP literal | Rejects private, loopback, link-local, reserved, multicast |
| DNS resolution | Resolves hostname; **rejects if any A/AAAA record is non-public** |
| **Redirect chain** | **Every redirect hop re-validated via the same DNS-aware check (TD-019 closed)** |

The `build_safe_session()` factory attaches a `_redirect_hook` to every `requests.Session` used for URL fetching, so no redirect can bypass the initial SSRF guard.

### Remaining Limitations

- Uses stdlib `socket.getaddrinfo` without custom timeout/TTL cache (ponytail ceiling — Phase 2)
- No per-org URL allowlist (enterprise feature, Phase 2)

### Testing

DNS and redirect checks use injectable `resolver` parameters and `unittest.mock.patch` for full coverage without network I/O.

---

## Upload Security

`/api/data/upload/` and `/api/data/upload-link/` enforce:

| Check | Mechanism |
|-------|-----------|
| File extension | `.csv`, `.xlsx`, `.xls` only (suffix check before write) |
| File size | Default 25 MB limit — configurable via `MAX_UPLOAD_MB` env var |
| Django layer limit | `DATA_UPLOAD_MAX_MEMORY_SIZE` = `MAX_UPLOAD_BYTES` (rejects at parse time) |
| MIME type | `mimetypes.guess_type()` validates after save — rejects non-CSV/Excel MIME types |
| Schema validation | Requires 2+ columns; ads-mode columns detected and validated |

---

## Rate Limiting

All API endpoints are throttled via DRF's built-in throttle system:

| Scope | Anonymous | Authenticated |
|-------|-----------|---------------|
| Global | 60/minute | 120/minute |
| `/api/chat/` | 20/minute | 40/minute |
| `/api/data/upload/` | 10/minute | 20/minute |
| `/api/data/upload-link/` | 10/minute | 20/minute |

All rates are configurable via environment variables (see `.env.example`).

---

## Chat Sessions

- **Authenticated users**: session ownership enforced by user FK (`ADR-005`)
- **Anonymous users**: session bound to Django `session_key` — resumed sessions require matching browser session (TD-003 closed)

---

## Production Checklist

- [x] Set `DJANGO_SECRET_KEY` — enforced at startup via `DJANGO_ENV`
- [x] Set `DEBUG=False` — enforced at startup via `DJANGO_ENV`
- [x] Restrict `ALLOWED_HOSTS` — enforced in staging/production
- [x] DNS-aware SSRF on URL ingest — `url_safety.py` + DNS resolution
- [x] SSRF redirect protection — `build_safe_session()` redirect hook
- [x] Upload size limit — `MAX_UPLOAD_MB` + `DATA_UPLOAD_MAX_MEMORY_SIZE`
- [x] Upload MIME validation — `mimetypes` check
- [x] Rate limiting — DRF throttle classes on all resource-intensive endpoints
- [x] Anonymous session isolation — `session_key` bound on create
- [ ] API authentication (tokens/keys) — Phase 2 M2 (TD-004)
- [ ] HTTPS enforcement — configure at reverse proxy / load balancer level
