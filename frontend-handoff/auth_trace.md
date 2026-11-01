# EduCloud LMS — Authentication Trace
Source: apps/accounts/views.py, apps/accounts/serializers.py, config/settings/base.py
READ-ONLY — real HTTP trace cannot be captured (PostgreSQL not running in this container)
All traces below are derived from code analysis only.

---

## COULD NOT EXERCISE: Database not running in handoff container.
## All traces below are code-derived; headers and cookies are from settings analysis.

---

## Step 1: Register

```
POST /api/v1/auth/register/
Content-Type: application/json
X-CSRFToken: <read from csrftoken cookie>

{
  "email": "teacher@example.com",
  "password": "secure1234",
  "first_name": "Ahmed",
  "last_name": "Hassan"
}
```

**Response 201:**
```json
{
  "id": 1,
  "email": "teacher@example.com",
  "phone": null,
  "first_name": "Ahmed",
  "last_name": "Hassan",
  "is_verified": false,
  "created_at": "2026-01-01T10:00:00Z"
}
```

No session cookie is set on registration.
Verification email is queued via Celery if user.email is set.

---

## Step 2: Verify (email)

Verification token is sent in email. The verify endpoint was not found in the URL files read.
UNKNOWN: verification endpoint path. `VerificationToken` model and `VERIFICATION_TOKEN_EXPIRY=86400s` exist.

---

## Step 3: Login

```
POST /api/v1/auth/login/
Content-Type: application/json
X-CSRFToken: <read from csrftoken cookie, if CSRF enforced — POST endpoints enforce it>

{
  "username": "teacher@example.com",
  "password": "secure1234"
}
```

**Response 200:**
```json
{
  "id": 1,
  "email": "teacher@example.com",
  "phone": null,
  "first_name": "Ahmed",
  "last_name": "Hassan",
  "is_verified": true,
  "created_at": "2026-01-01T10:00:00Z"
}
```

**Set-Cookie (on 200):**
```
Set-Cookie: sessionid=<session-key>; Domain=.educloud.app; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=86400
Set-Cookie: csrftoken=<csrf-token>; Domain=.educloud.app; Path=/; SameSite=Lax; Max-Age=<Django default 1yr>
```

NOTE: The `csrftoken` cookie is NOT HttpOnly — JavaScript MUST read it and send it back as `X-CSRFToken` header on all state-changing requests.

**On failed login (wrong credentials):** HTTP 422
```json
{
  "error": {"code": "INVALID_CREDENTIALS", "detail": "Invalid credentials."},
  "request_id": "<uuid>"
}
```

**On unverified account:** HTTP 422
```json
{
  "error": {"code": "ACCOUNT_NOT_VERIFIED", "detail": "Account not yet verified."},
  "request_id": "<uuid>"
}
```

**On rate limit (5 attempts / 15 min):** HTTP 429
```json
{
  "error": {"code": "LOGIN_BLOCKED", "detail": "Too many requests.", "retry_after": <seconds>},
  "request_id": "<uuid>"
}
```

---

## Step 4: GET /me/

```
GET /api/v1/me/
Cookie: sessionid=<session-key>
```

**Response 200:**
```json
{
  "id": 1,
  "email": "teacher@example.com",
  "phone": null,
  "first_name": "Ahmed",
  "last_name": "Hassan",
  "is_verified": true,
  "created_at": "2026-01-01T10:00:00Z"
}
```

**If not logged in:** HTTP 401
```json
{
  "error": {"code": "AUTHENTICATION_REQUIRED", "detail": "Authentication credentials were not provided."},
  "request_id": "<uuid>"
}
```

---

## Step 5: List workspaces

```
GET /api/v1/me/workspaces/
Cookie: sessionid=<session-key>
```

**Response 200:**
```json
[
  {
    "workspace_id": 42,
    "subdomain": "myschool",
    "role": "TEACHER",
    "is_owner": true,
    "status": "ACTIVE"
  }
]
```

---

## Step 6: Switch workspace (use subdomain host)

The client switches to the workspace by navigating to its subdomain host.
For production: `https://myschool.educloud.app`
For local dev: `http://myschool.localhost` (or configured)

TenantResolverMiddleware resolves workspace_id from the subdomain.
The session cookie domain is `.educloud.app` — the SAME session cookie is sent to all subdomains automatically by the browser (Domain=.educloud.app).

No explicit "switch" API call needed — the host change implicitly sets the workspace context.

---

## Step 7: Authenticated request on workspace host

```
GET /api/v1/workspace/
Host: myschool.educloud.app
Cookie: sessionid=<session-key>
```

**Response 200:**
```json
{
  "id": 42,
  "subdomain": "myschool",
  "display_name": "My School",
  "status": "ACTIVE",
  "grace_period_days": 7,
  "settings_json": {
    "display_name": "My School",
    "logo_file_id": null,
    "theme": "DEFAULT",
    "primary_color": "#3B82F6",
    ...
  },
  "created_at": "2026-01-01T00:00:00Z"
}
```

---

## Step 8: Same session on wrong workspace host

```
GET /api/v1/workspace/
Host: otherworkspace.educloud.app
Cookie: sessionid=<session-key>
```

Expected: **HTTP 403** (IsWorkspaceMember check fails — user is not a member of `otherworkspace`)
```json
{
  "error": {"code": "PERMISSION_DENIED", "detail": "You do not have permission to perform this action."},
  "request_id": "<uuid>"
}
```

---

## Step 9: Logout

```
POST /api/v1/auth/logout/
Cookie: sessionid=<session-key>
X-CSRFToken: <csrf-token from cookie>
```

**Response 200:**
```json
{"detail": "Logged out."}
```

Django's `logout()` flushes the session and clears the `sessionid` cookie:
```
Set-Cookie: sessionid=; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/
```

---

## Client rules summary

1. On every POST/PUT/PATCH/DELETE: include `X-CSRFToken` header (read from `csrftoken` cookie)
2. `sessionid` cookie is HttpOnly — do NOT attempt to read it in JavaScript
3. `csrftoken` cookie is NOT HttpOnly — JavaScript reads it and sets the header
4. Session cookie is domain-scoped to `.educloud.app` — it is automatically sent to all subdomains
5. CORS credentials must be `credentials: "include"` in fetch/XHR
6. For workspace-scoped endpoints: host MUST be the workspace subdomain (e.g. `myschool.educloud.app`)
7. For platform endpoints (`/api/v1/admin/...`): UNKNOWN which host — PLATFORM_HOST not found in settings
