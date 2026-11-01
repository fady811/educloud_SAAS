# EduCloud LMS — Deviations from Blueprint
Source: code only — comparing BACKEND_ENGINEERING_BLUEPRINT.md intent against actual implementation
READ-ONLY snapshot — do not fix; just document

---

## DEV-001: CourseWriteSerializer uses invalid default "PRIVATE" for visibility

**Blueprint:** Visibility choices are DRAFT, PUBLISHED, ARCHIVED (core/enums.py:51-54)
**Code:** `CourseWriteSerializer` (apps/content/serializers.py:32) sets `default="PRIVATE"` for the `visibility` field
**Impact:** POST /api/v1/courses/ with no visibility field will attempt to save "PRIVATE" as a visibility value, which is NOT in the Visibility TextChoices enum. This will cause a database validation error or silently store an invalid value.
**Severity:** CONTRACT-BREAKING — creates/edits will fail or produce invalid data
**HTTP contract change:** Yes — field default is invalid

---

## DEV-002: PLATFORM_HOST not defined in settings

**Blueprint (§15.5):** Platform admin API served on a platform host, distinct from workspace subdomains
**Code:** `PLATFORM_HOST` variable does not exist in `config/settings/base.py` or `config/settings/local.py`
**Impact:** No host isolation for `/api/v1/admin/` endpoints. Any host can hit them if user has `is_super_admin=True`. TenantResolverMiddleware behavior was not read — may or may not provide isolation.
**Severity:** BEHAVIOURAL — security model for admin endpoints is weaker than specified
**HTTP contract change:** No (endpoint paths unchanged)

---

## DEV-003: Arabic error messages not implemented

**Blueprint (CON-01):** Arabic as primary language; error messages should be in Arabic
**Code:** All `detail` strings in domain exceptions and exception_handler are English. `LANGUAGE_CODE="ar"` is set but no Arabic translations or message templates were found in any file read.
**Impact:** All error responses return English strings
**Severity:** BEHAVIOURAL — UX impact for Arabic-speaking users
**HTTP contract change:** No (field names/codes unchanged)

---

## DEV-004: Password reset endpoints not in accounts/urls.py

**Blueprint:** Password reset flow (REQ-SEC-03)
**Code:** `PasswordResetRequestSerializer` and `PasswordResetConfirmSerializer` exist in `apps/accounts/serializers.py`, but no password reset URL paths were found in `apps/accounts/urls.py`. Only these paths exist: register, login, logout, sessions, me, me/workspaces.
**Impact:** Password reset cannot be exercised via API — endpoints do not exist at the URL level
**Severity:** CONTRACT-BREAKING — functionality missing from URL routing
**HTTP contract change:** Yes — endpoints are absent

---

## DEV-005: Email verification endpoint not in accounts/urls.py

**Blueprint:** Email verification flow after registration (REQ-SEC-01)
**Code:** `VerificationToken` model exists; `send_verification_email` task is called on registration; but no verification URL path was found in any of the url files read.
**Impact:** Users cannot verify their email via the API
**Severity:** CONTRACT-BREAKING — registration flow is incomplete (user gets `is_verified=False`, no way to flip it)
**HTTP contract change:** Yes — verification endpoint absent

---

## DEV-006: SessionRevokeView handles two separate URL patterns with one class

**Blueprint:** Separate endpoints for single-session revoke and revoke-all-others
**Code:** Both `auth/sessions/<int:pk>/` (DELETE) and `auth/sessions/revoke-others/` (POST) route to `SessionRevokeView`. The class handles both with different HTTP methods. The URL `auth/sessions/revoke-others/` also registers `name="session-revoke-others"` but uses the same view class.
**Impact:** Cosmetic; both paths work correctly per code
**Severity:** COSMETIC
**HTTP contract change:** No

---

## DEV-007: adminconsole views use non-existent User.full_name and User.date_joined

**Blueprint:** User model fields
**Code:** `UserListView` (apps/adminconsole/views.py:65-66) references `u.full_name` and `u.date_joined`. The User model as read has `first_name`, `last_name`, `display_name` (property), and `created_at` — no `full_name` field and no `date_joined` field. `date_joined` is from Django's AbstractUser which this model does NOT inherit from (it uses AbstractBaseUser).
**Impact:** `GET /api/v1/admin/users/` will raise AttributeError on any user object
**Severity:** CONTRACT-BREAKING — this endpoint will 500 on any user
**HTTP contract change:** Yes — endpoint is broken

---

## DEV-008: SubscriptionPaymentSerializer field name mismatch

**Blueprint:** Payment rejection uses `rejection_reason`
**Code:** `SubscriptionPayment` model has field `rejection_reason` (apps/billing/models.py:83, blank field). But `SubscriptionPaymentViewSet.reject()` sets `payment.notes = reason` not `payment.rejection_reason`. The serializer exposes `rejection_reason` — so `rejection_reason` will always be blank in the serialized response; the actual reason is in `notes` which is not in the serializer.
**Impact:** Frontend reads `rejection_reason` from the API → always empty; actual reason is lost in `notes`
**Severity:** BEHAVIOURAL
**HTTP contract change:** No (field exists, just wrong value)

---

## DEV-009: MessageViewSet.list() uses MD5 for ETag (weak hash)

**Blueprint:** ETag support for message polling
**Code:** Uses `hashlib.md5(...)` for ETag. MD5 is a weak hash but is valid for ETag purposes (collision resistance not required for ETags). No security concern for this use case.
**Severity:** COSMETIC — not a security or contract issue

---

## DEV-010: `notes` field in SubscriptionPayment serializer is absent

**Code:** `SubscriptionPaymentSerializer` does NOT include `notes` in its field list. But `reject()` and `approve()` both write to `payment.notes`. The written value is never returned to the client.
**Severity:** BEHAVIOURAL — clients cannot read approved/rejection notes

---

## DEV-011: CourseWriteSerializer accepts `subject_id` but Course model has `subject` (FK)

**Code:** `CourseWriteSerializer` field is `subject_id = serializers.IntegerField(required=False, allow_null=True)`. Django will pass `subject_id` to `Course.objects.create(...)` which works correctly (Django model accepts `subject_id` as the FK column). This is correct behavior, not a bug.
**Severity:** NOT A DEVIATION — works correctly

---

## DEV-012: WorkspaceMembershipSerializer references `joined_at` which is not a model field

**Code:** `WorkspaceMembershipSerializer` (apps/workspaces/serializers.py:54) has `joined_at = serializers.DateTimeField()`. `WorkspaceMembership` model does not have a `joined_at` field — only `created_at` (from TimeStampedModel). Without `source="created_at"`, this will raise a serializer error when called.
**Impact:** Any code path that uses `WorkspaceMembershipSerializer` with a real instance will 500
**Severity:** CONTRACT-BREAKING — serializer is broken (though this serializer is not used in any view read)
**HTTP contract change:** Indirect — any future view using it will fail

---

## DEV-013: `SESSION_COOKIE_NAME` not explicitly set

**Blueprint (§15.2):** Session cookie configuration
**Code:** Django default `sessionid` is used (no explicit override)
**Severity:** COSMETIC — frontend just reads whatever cookie name Django issues; no contract impact

---

## DEV-014: `API_THROTTLE_RATE` env var controls BOTH anon and user rates

**Code:** Both `anon` and `user` throttle rates use the same `_env("API_THROTTLE_RATE", ...)` call with different defaults. If `API_THROTTLE_RATE` is set in production, both anon (100/h default) and user (1000/h default) are overridden to the SAME value. This may be intentional but is surprising.
**Severity:** BEHAVIOURAL — may affect rate limits in production

---

## NOTES

- Service files not read — additional deviations may exist in business logic
- These deviations were found from reading source code only, not from running tests
