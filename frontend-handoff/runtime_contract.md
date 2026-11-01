# EduCloud LMS — Runtime Contract
Source: config/settings/base.py + config/settings/local.py + apps/core/pagination.py
READ-ONLY snapshot

---

## Pagination

### Default class: `apps.core.pagination.PageNumberPagination`
- Default page size: **25**
- `page_size` query param: `page_size`
- Max page size: **200**
- Page query param: `page`
- Response envelope:
  ```json
  {
    "count": <total>,
    "next": "<url or null>",
    "previous": "<url or null>",
    "results": [...]
  }
  ```

### Cursor pagination: `apps.core.pagination.CursorPagination`
Used for: MessageViewSet (append-heavy lists)
- Default page size: **50**
- Ordering: `-created_at`
- Cursor query param: `cursor`

Endpoints using cursor pagination: NOT explicitly confirmed in views; class exists and is available for use. MessageViewSet does not declare `pagination_class` in the read code — uses default PageNumberPagination unless set elsewhere.

---

## Session Cookie

| Property | Value |
|---|---|
| Cookie name | `sessionid` (Django default — NOT explicitly set in settings) |
| Domain | `.educloud.app` (production), `None` (local dev overrides to None) |
| HttpOnly | `True` |
| Secure | `True` in production (DEBUG=False), `False` in local dev |
| SameSite | `Lax` |
| Max-Age | `86400` seconds (24 hours), configurable via `SESSION_COOKIE_AGE` env var |
| Backend | DB-backed (`django.contrib.sessions.backends.db`) |
| Save on every request | `False` |

---

## CSRF

| Property | Value |
|---|---|
| Cookie name | `csrftoken` (Django default — NOT explicitly set) |
| HttpOnly | `False` — JavaScript MUST read this cookie to send the header |
| Secure | `True` in production, `False` in local dev |
| SameSite | `Lax` |
| Request header expected | `X-CSRFToken` |
| Methods enforcing CSRF | POST, PUT, PATCH, DELETE (Django standard — GET/HEAD/OPTIONS exempt) |
| Trusted origins (prod) | `https://*.educloud.app`, `https://educloud.app` |
| Trusted origins (local) | `http://localhost:3000`, `http://127.0.0.1:3000` |

---

## CORS

| Property | Value |
|---|---|
| Allowed origins (prod) | Regex: `^https://[\w-]+\.educloud\.app$` and `^https://educloud\.app$` |
| Allowed origins (local) | Regex: `^http://localhost:\d+$` and `^http://127\.0\.0\.1:\d+$` |
| Allow credentials | `True` |
| Allowed headers | `accept, authorization, content-type, x-csrftoken, x-request-id, idempotency-key` |
| IMPORTANT | Production CORS does NOT allow localhost or any port variant. Local dev uses a separate settings override. |

---

## Throttling

### Global defaults (DRF DEFAULT_THROTTLE_CLASSES)
- Anonymous: `100/hour` (configurable via `API_THROTTLE_RATE` env var)
- Authenticated user: `1000/hour` (same env var — both use same value)

### Custom scopes (DEFAULT_THROTTLE_RATES)
| Scope | Rate |
|---|---|
| `registration` | 10/hour |
| `password_reset` | 3/hour |
| `subdomain_check` | 30/minute |
| `invite_link` | 20/minute |
| Login (custom sliding-window) | 5 attempts per 900 seconds (15 min) per IP |

### Login throttle specifics
- Class: `LoginThrottle` (custom, in apps/accounts/views.py)
- Algorithm: sliding window (keeps timestamps in Redis cache)
- Max attempts: `LOGIN_THROTTLE_MAX_ATTEMPTS` (default 5)
- Window: `LOGIN_THROTTLE_WINDOW_SECONDS` (default 900s = 15 min)
- Retry-After: available via `ThrottledError.retry_after` — seconds to wait
- On Redis failure: **fails open** (user is NOT blocked)
- Proxy awareness: `NUM_PROXIES=1` in production — uses XFF rightmost-trusted IP

### Retry-After header
DRF standard Throttle returns `Retry-After` header.
Custom ThrottledError includes `retry_after` in the error body's `extra` dict.

---

## Signed URL TTLs

| Category | TTL | Use case |
|---|---|---|
| Content (lesson videos, documents) | **7200 seconds (2 hours)** | `SIGNED_URL_TTL_CONTENT` |
| Payment proof images | **900 seconds (15 minutes)** | `SIGNED_URL_TTL_PROOF` |

---

## Upload Limits

| Setting | Value |
|---|---|
| Max file size | **500 MB** (configurable via `DEFAULT_UPLOAD_SIZE_LIMIT_MB`) |

### Allowed MIME types per category

| Category | Allowed MIME types |
|---|---|
| `LESSON_VIDEO` | `video/mp4`, `video/webm`, `video/quicktime` |
| `LESSON_DOCUMENT` | `application/pdf` |
| `LESSON_ATTACHMENT` | `application/pdf`, `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `application/zip`, `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `BRANDING_LOGO` | (same as LESSON_ATTACHMENT — UNKNOWN, no specific override seen) |
| `PAYMENT_PROOF` | (same as image types — UNKNOWN specific) |
| SVG | **REJECTED** (DR-041, INV-95a) |

### Multipart upload
- DRF parsers include `MultiPartParser` and `FormParser` — multipart IS configured
- Upload flow: client calls `/api/v1/files/upload/` (POST JSON with filename, content_type, category, size_bytes) → receives presigned URL → client PUTs directly to storage
- **Presigned upload is implemented for R2/local storage** — actual PUT goes to storage, NOT to Django

---

## Storage Backend

| Env | Backend | URL |
|---|---|---|
| Production | `r2` (Cloudflare R2 / S3-compatible) | `https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com` |
| Local dev | `local` | `/media/` (Django-served) |

---

## Virus Scanning

- Default backend: `null` (no scanning)
- Production options: `clamav` or `eicar_only`
- Callback endpoint: `POST /api/v1/files/{id}/scan-callback/` — secured by `X-Scanner-Secret` header (shared secret HMAC)
- If `SCANNER_CALLBACK_SECRET` not configured: all callbacks are rejected (fail-closed)

---

## Local Dev Configuration

| Setting | Local dev value |
|---|---|
| BASE_DOMAIN | `localhost` |
| WORKSPACE_DOMAIN_SUFFIX | `.localhost` |
| SESSION_COOKIE_DOMAIN | `None` (no domain pinning) |
| SESSION_COOKIE_SECURE | `False` |
| CSRF_COOKIE_SECURE | `False` |
| CSRF_TRUSTED_ORIGINS | `http://localhost:3000`, `http://127.0.0.1:3000` |
| CORS allowed | `http://localhost:<any port>`, `http://127.0.0.1:<any port>` |
| STORAGE_BACKEND | `local` |
| EMAIL_BACKEND | console |
| SECRET_KEY | `local-dev-secret-key-not-for-production` |

PLATFORM_HOST: NOT found in any settings file. Blueprint mentions it; code does not define it.
The platform-admin API is served from any host (no host guard in code); the TenantResolverMiddleware logic was not read.

---

## Token Expiry

| Token | TTL |
|---|---|
| Verification token (email/phone) | 86400 seconds (24 hours) |
| Password reset token | 3600 seconds (1 hour) |
| Invite link | 14 days |
| Team invitation | 7 days |
| Parent linking code | 14 days |

---

## Session Limits per Role

| Role | Max concurrent sessions |
|---|---|
| STUDENT | 3 |
| PARENT | 3 |
| TEACHER | 5 |
| TEAM_MEMBER | 5 |
| SUPER_ADMIN | 10 |

---

## Money / Decimal

All `DecimalField` values are serialized as **strings** (`COERCE_DECIMAL_TO_STRING=True`).
Example: `"price_egp": "299.00"` not `299.0`.

---

## Localization

- `LANGUAGE_CODE = "ar"` (Arabic)
- `TIME_ZONE = "Africa/Cairo"` (UTC+2 / UTC+3 DST)
- `USE_TZ = True` — all timestamps stored as UTC-aware; displayed in Africa/Cairo
- API timestamps are ISO 8601 with timezone info

---

## Request ID

All error responses include `"request_id": "<uuid>"`.
Clients may send `X-Request-ID` header; middleware attaches it.
Response header: UNKNOWN (logging module was not read).

---

## Idempotency Key

Header `idempotency-key` is in CORS allowed headers.
`IdempotencyKey` model exists in `apps/core/idempotency.py`.
Which endpoints enforce it: UNKNOWN (service code not read).

---

## ETag / Polling

MessageViewSet.list() implements ETag:
- Computes `MD5([id, ...])` of message IDs
- Returns `ETag` response header
- Honors `If-None-Match` request header → returns `304 Not Modified` if unchanged
- No polling interval is hardcoded in the code read. Client should choose an interval.

---

## Export/Import limits

| Setting | Value |
|---|---|
| CSV import row limit | 1000 rows |
| Export row cap | 10,000 rows |

---

## Celery queues

| Queue | Task pattern |
|---|---|
| `high` | `apps.accounts.tasks.*` |
| `files` | `apps.files.tasks.*` |
| `default` | all others |
