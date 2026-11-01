# Fixes Changelog

Branch: `fix/authorization-and-contract-bugs`

---

## Part 1 — Authorization Hardening

### 1.1 — Added `WorkspacePermission` with declarative `permission_map`

**File:** `apps/core/permissions.py`

Added role constants (`ALL_MEMBERS`, `STAFF_ONLY`, `NON_PARENT`, `STUDENT_ONLY`, `PARENT_ONLY`) and a
`WorkspacePermission` class that reads a view's `permission_map` and enforces role + permission-key
checks declaratively. Super-admins bypass all checks; owners bypass `required_permission_key` checks.

**HTTP contract impact:** None for compliant callers. Previously any workspace member could call any
endpoint regardless of role; now 403 is returned for callers who lack the declared role or key.

---

### 1.2 — Converted all workspace views to `WorkspacePermission`

**Files:** `apps/content/views.py`, `apps/groups/views.py`, `apps/assessments/views.py`,
`apps/enrollment/views.py`, `apps/communication/views.py`, `apps/payments/views.py`,
`apps/reports/views.py`, `apps/support/views.py`, `apps/parents/views.py`, `apps/files/views.py`

Every view now declares `permission_classes = [WorkspacePermission]` and a `permission_map` dict.
Removed all inline `has_permission()` checks that duplicated or replaced the class-level gate
(parents/views.py previously called `has_permission()` inside the handler; this is now handled by
`permission_map`).

**HTTP contract impact:** As above — 403 for unauthorized roles/keys; no change for authorized callers.

---

### 1.3 — Enrollment self-only rule for students

**File:** `apps/enrollment/views.py`

Students may only create enrollments for themselves (`student_id == request.user.id`); otherwise 403.
Non-students need `STUDENT_EDIT` to enroll any student. Target must be a `STUDENT` member (else 422).
`check_limit(workspace_id, LimitKey.MAX_STUDENTS, ...)` called before creating; 409 if over limit.

**HTTP contract impact:** POST `/enrollment/enrollments/` — students enrolling other students now 403 (was 201).

---

### 1.4 — Draft/Archived content filtered for STUDENT/PARENT

**File:** `apps/content/views.py`

`CourseListCreateView.get()` and `LessonListCreateView.get()` filter to `visibility=PUBLISHED` for
STUDENT/PARENT callers.

**HTTP contract impact:** GET `/content/courses/` — STUDENT/PARENT now see only published courses.

---

## Part 2 — Contract Bugs

### Bug 2.1 — `CourseWriteSerializer.visibility` invalid default

**File:** `apps/content/serializers.py`

Changed `visibility = serializers.CharField(required=False, default="PRIVATE")` to
`serializers.ChoiceField(choices=["DRAFT","PUBLISHED","ARCHIVED"], required=False, default="DRAFT")`.

`"PRIVATE"` is not a valid `Visibility` enum value; would have stored a corrupt value in the DB.
Default is now `DRAFT` (correct).

**HTTP contract impact:** POST `/content/courses/` without `visibility` now stores `DRAFT` (was storing
`"PRIVATE"`, which would fail at the DB constraint level). `"PRIVATE"` is now rejected with 400.

---

### Bug 2.2 — `UserListView` ordering and field names

**File:** `apps/adminconsole/views.py`

Changed:
- `.order_by("-date_joined")` → `.order_by("-created_at")` (User model has `created_at`, not `date_joined`)
- `u.full_name` → `u.display_name` (User model has `display_name` property, not `full_name`)
- `u.date_joined` → `u.created_at`

Both attribute accesses would raise `AttributeError` on every request (HTTP 500).

**HTTP contract impact:** GET `/admin/users/` now returns 200 (was 500). Response keys changed:
`full_name` → `display_name`, `date_joined` → `created_at`.

---

### Bug 2.3 — `WorkspaceMembershipSerializer.joined_at` missing source

**File:** `apps/workspaces/serializers.py`

Changed `joined_at = serializers.DateTimeField()` to
`joined_at = serializers.DateTimeField(source="created_at", read_only=True)`.

`WorkspaceMembership` inherits from `TimeStampedModel` and has `created_at`; there is no `joined_at`
field. The field would raise `AttributeError` on every serialization (HTTP 500).

**HTTP contract impact:** All membership-listing responses now return a valid `joined_at` timestamp
(was 500).

---

### Bug 2.4 — `billing/views.py` reject action writes to non-existent `notes` field

**File:** `apps/billing/views.py`

Changed:
- `reject` action: `payment.notes = reason` / `update_fields=[..."notes"...]` →
  `payment.rejection_reason = reason` / `update_fields=[..."rejection_reason"...]`
- `approve` action: removed `payment.notes = notes` / `"notes"` from `update_fields`
  (`SubscriptionPayment` has no `notes` field — only `rejection_reason`)

Both writes would raise `ValueError: The following fields do not exist in this model: notes`.

**HTTP contract impact:** POST `/billing/payments/{id}/reject` now returns 200 (was 500).
POST `/billing/payments/{id}/approve` no longer attempts to save internal notes (field doesn't exist).

---

### Bug 2.5 — Middleware docstring tenant-isolation hole

**File:** `apps/core/tenancy/middleware.py`

Deleted the line `1. X-Workspace-ID header (for internal/admin requests — only on platform host)`
from the docstring. No such header is implemented; advertising it could lead to an implementation
that bypasses tenant isolation.

**HTTP contract impact:** None (docstring only).

---

## Part 3 — Login Throttle Fail-Closed

**File:** `apps/accounts/services/login_throttle.py`

Wrapped all `cache.get()` / `cache.set()` calls in try/except. On cache failure, an in-process
dict (`_fallback_counts`) is used so the throttle still blocks after 5 attempts (fail-closed).

**Limitation:** In-process counters are not shared across workers and do not survive restarts.
A DB-backed counter is preferable but requires a migration. See `OPEN_QUESTIONS.md`.

**HTTP contract impact:** POST `/auth/login/` — a Redis outage previously caused unhandled exceptions
or failed open; now correctly throttles using the in-process fallback.
