# EduCloud LMS — Frontend Questions (B1–B33)
Source: code only — all answers from reading source files
READ-ONLY snapshot

---

## Auth / Tenancy

**B1. How does multi-tenancy work?**
Subdomain-based. `TenantResolverMiddleware` (in middleware stack) extracts the workspace from the request host's subdomain (e.g. `myschool.educloud.app` → workspace with subdomain `myschool`). The resolved `workspace_id` is attached to `request.workspace_id`. All `TenantModel` records include a `workspace_id` FK. The middleware file was not read — exact resolution logic is UNKNOWN, but the URL config and workspace subdomain field confirm this approach.

**B2. Does the session cookie survive workspace switches?**
Yes. The session cookie domain is `.educloud.app` (with leading dot) — browsers send it to ALL subdomains automatically. Switching from `myschool.educloud.app` to `otherschool.educloud.app` sends the same session. Authorization (IsWorkspaceMember) then rejects the user if not a member of the new workspace.

**B3. Do I need to call a "switch workspace" endpoint?**
No. The workspace context is entirely determined by the HTTP host. Navigate to `myschool.educloud.app` and all requests on that host are scoped to that workspace. No explicit switch API call.

**B4. What happens if a non-member hits a workspace endpoint?**
HTTP 403, code `PERMISSION_DENIED`.

**B5. What triggers 401 vs 403?**
- 401: unauthenticated (no session, or session expired) — code `AUTHENTICATION_REQUIRED`
- 403: authenticated but lacking permission — code `PERMISSION_DENIED`
Note: DRF uses NotAuthenticated → 401, PermissionDenied → 403 in the exception handler.

**B6. Is the CSRF cookie set on login, or does the client need to GET any page first?**
UNKNOWN — the exact point Django sets the CSRF cookie was not traced. Django typically issues the CSRF cookie on any GET request. The frontend should make at least one GET (e.g. GET /api/v1/me/ or GET /api/v1/packages/) before POSTing to get the cookie. Alternatively, check if Django's CsrfViewMiddleware issues it on the first request.

**B7. What is the session limit enforcement behavior?**
`SESSION_LIMITS` defines max concurrent sessions per role (STUDENT: 3, PARENT: 3, TEACHER: 5, TEAM_MEMBER: 5, SUPER_ADMIN: 10). Enforcement is in `apps/accounts/services/sessions.py` which was not read. UNKNOWN whether oldest session is evicted or login is rejected.

---

## Data conventions

**B8. All decimal/money fields come as strings?**
Yes. `COERCE_DECIMAL_TO_STRING = True`. Every `DecimalField` is serialized as a quoted string (e.g. `"150.00"`, not `150.0`).

**B9. Timestamp format?**
ISO 8601, timezone-aware (UTC). Example: `"2026-01-15T09:30:00Z"`. `USE_TZ=True`, `TIME_ZONE="Africa/Cairo"` but storage is UTC.

**B10. Null vs missing fields?**
DRF serializers always include all declared fields. Nullable fields come as `null`, not absent.

**B11. Are list endpoints paginated?**
Inconsistent:
- ViewSet-based views (using DefaultRouter / GenericViewSet): use default `PageNumberPagination` (page_size=25, max=200)
- APIView-based views (GroupListCreateView, SubjectListCreateView, CourseListCreateView, etc.): return raw list with no pagination wrapper

See url_inventory.csv column `pagination_class` for per-endpoint status.

**B12. How do I get all pages?**
Use `?page=N&page_size=200` (max). Paginated responses include `count`, `next`, `previous` URL links.

---

## Files / Video / Exams

**B13. What is the upload flow?**
POST JSON to `/api/v1/files/upload/` (filename, content_type, category, size_bytes) → receive presigned PUT URL → client PUTs bytes directly to R2/storage → poll GET `/api/v1/files/{id}/` until `scan_status` is not `PENDING`.

**B14. Does Django receive file bytes?**
No. Only the JSON metadata. File bytes go directly to R2 (production) or local storage (dev).

**B15. How do I display a video?**
GET `/api/v1/files/{id}/` — the `url` field is a presigned URL valid for 2 hours (`SIGNED_URL_TTL_CONTENT=7200`). Use it directly in a `<video src="...">`. Re-fetch if URL expires.

**B16. When is a file usable?**
When `scan_status = "CLEAN"` (or `SKIPPED` in null-scanner dev mode). Do not display/link PENDING or INFECTED files.

**B17. Can students see correct answers?**
No. `correct_answer` field is on the Question model but `QuestionSerializer` does NOT include it. Students receive: `id, exam, question_type, body, choices, points, display_order`.

**B18. How is exam timing enforced?**
Server-authoritative. `ExamAttempt.deadline_at` is set by the server at `start_attempt()`. Client should display a timer based on `deadline_at`. Server rejects submissions after `deadline_at` with code `ATTEMPT_EXPIRED` (defined in ErrorCode).

---

## Billing

**B19. Who pays whom?**
Two separate payment flows:
1. Teacher → EduCloud: subscription payments (`SubscriptionPayment`) reviewed by Super Admins
2. Student → Teacher: student payments (`StudentPayment`) reviewed by workspace staff

**B20. Are payments real-time (gateway) or manual proof?**
Manual proof submission. Teacher/student uploads a payment screenshot (proof_file_id) → reviewed by appropriate party → APPROVED/REJECTED. No payment gateway integration in the code read.

**B21. What is a CapacityAddon?**
One-time top-up purchase (e.g. extra student slots, extra storage GB) — `AddonType`: STUDENT_SLOTS, STORAGE_GB.

---

## Localization

**B22. What language is the API in?**
Error messages are in English (all detail strings in exception classes). `LANGUAGE_CODE="ar"` is set but no Arabic templates were found in the code read. This is a DEVIATION from blueprint intent.

**B23. Are field names in Arabic?**
No. All field names are English snake_case.

**B24. Timezone handling?**
API sends UTC timestamps. The client is responsible for displaying them in Africa/Cairo (UTC+2/+3 with DST) if needed.

---

## Local development

**B25. What settings change in local dev?**
See runtime_contract.md "Local Dev Configuration" section. Key differences: CORS allows localhost, SESSION_COOKIE_DOMAIN=None, STORAGE_BACKEND=local, no HTTPS required.

**B26. What BASE_DOMAIN is used locally?**
`BASE_DOMAIN = "localhost"`, `WORKSPACE_DOMAIN_SUFFIX = ".localhost"`. Workspace subdomains would be `myschool.localhost`.

**B27. How to hit workspace endpoints locally?**
The host must resolve to the correct subdomain. Options:
- Add `myschool.localhost 127.0.0.1` to /etc/hosts
- Use a proxy that sets the Host header
- UNKNOWN if TenantResolverMiddleware has a fallback for local dev

**B28. Does CORS allow localhost?**
YES — but only in local dev settings (`config/settings/local.py` overrides CORS). Production settings do NOT allow localhost. See runtime_contract.md.

**B29. Is there a PLATFORM_HOST setting?**
NOT FOUND in any settings file read. Blueprint mentions it; implementation does not define it. Platform-admin endpoints (`/api/v1/admin/...`) appear to be accessible from any host — the TenantResolverMiddleware behavior for the platform host is UNKNOWN without reading that file.

---

## Honesty pass

**B30. What features are NOT implemented?**
Based on code read:
- Verification endpoint (not found in urls.py files read) — PARTIAL (model and service exist)
- Password reset endpoints (not in accounts/urls.py) — NOT IMPLEMENTED in URLs (serializers exist)
- Custom domain (model exists, logic "deferred" per code comment in CustomDomain model)
- ETag on messages only (other endpoints have no ETag)
- CSV student import endpoint (model exists, no URL found in accounts/urls.py)
- `EXPORT_FORMAT_NOT_SUPPORTED` error code exists but no export endpoint found

**B31. Which serializers are missing (UNKNOWN shape)?**
- `apps/enrollment/serializers.py` — not read
- `apps/payments/serializers.py` — not read
- `apps/communication/serializers.py` — not read
- `apps/support/serializers.py` — not read
- `apps/parents/serializers.py` — not read
- `apps/notifications/serializers.py` — not read
- `apps/billing/serializers.py` — WAS read

**B32. Which service files were not read?**
- All `apps/*/services/` subdirectories
- `apps/core/tenancy/middleware.py`
- `apps/core/logging.py`
- `apps/core/etag.py`
- `apps/files/services/upload.py` (upload presign response shape unknown)
- `apps/files/services/storage.py`

**B33. Are there any HTTP contract deviations from blueprint?**
See `deviations.md`. Notable ones:
- `PLATFORM_HOST` not implemented → platform admin endpoint host isolation unclear
- Arabic error messages not implemented
- `CourseWriteSerializer` defaults visibility to "PRIVATE" (not a valid Visibility choice — DRAFT is valid, PRIVATE is not in enum — see deviations.md)
- `SessionRevokeView` handles both `DELETE /{pk}/` and `POST /revoke-others/` with same class
