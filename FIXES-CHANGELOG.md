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

---

## Part 2 — Round 2: Read Holes, Regression Fix, DB Throttle, Full Test Matrix

### 2.1 — Fixed grade data leak: ExamAttempt and AssignmentSubmission querysets narrowed by role

**Files:** `apps/assessments/views.py`

`ExamAttemptViewSet.get_queryset()` and `AssignmentSubmissionViewSet.get_queryset()` previously returned all workspace records to every role, including STUDENT, allowing any student to read every other student's grades.

**Fix:**
- STUDENT: filtered to `student_id=request.user.id`
- PARENT: filtered to children via active `ParentStudentLink` rows
- TEACHER/TEAM_MEMBER/OWNER: unchanged (all records)

`retrieve` returns 404 (not 403) for unauthorized objects because the queryset is narrowed before DRF's object lookup.

### 2.2 — Fixed payment regression: STUDENT and PARENT now pass the GET permission gate

**Files:** `apps/payments/views.py`, `apps/core/permissions.py`

`StudentPaymentViewSet.permission_map["GET"]` had `required_permission_key: PAYMENT_VIEW` which blocked STUDENT entirely, making the student-narrowing code in `get_queryset` dead code.

**Fix:** Added `allow_roles_without_key: frozenset(["STUDENT", "PARENT"])` to the GET rule. STUDENT/PARENT bypass the key check; TEACHER/TEAM_MEMBER still need `PAYMENT_VIEW`.

`WorkspacePermission` was updated with a new `allow_roles_without_key` rule key. Also added PARENT narrowing to the payment queryset (own children's payments only).

### 2.3 — Replaced in-process throttle fallback with DB-backed LoginAttempt model

**Files:** `apps/accounts/models.py`, `apps/accounts/migrations/0003_loginattempt.py`, `apps/accounts/services/login_throttle.py`

The in-process dict fallback was not shared across Gunicorn workers (effective limit 5×N per worker) and reset on restart.

**Fix:**
- Added `LoginAttempt` model with `identifier_hash` (SHA-256 of email/phone, never raw), `ip_address`, `attempted_at`, and compound indexes on `(identifier_hash, attempted_at)` and `(ip_address, attempted_at)`.
- `record_failure` now writes a `LoginAttempt` row when the cache raises instead of incrementing an in-process dict.
- `check_login_allowed` and `is_locked` query the DB when the cache raises.
- Opportunistic `_db_cleanup()` deletes rows older than the 900-second window after each DB-path failure record.
- Redis remains the fast path; DB is fallback only.

### 2.4 — Full table-driven permission matrix tests (36 tests, all passing)

**Files:** `tests/test_permission_matrix.py`, `config/settings/test.py`

Rewrote the test file with 7 test classes covering:
- Structural: all WorkspacePermission views declare permission_map (4.1)
- Full matrix: 7 actors × major endpoints (4.2)
- Contract regression: bugs 2.1–2.3 (4.3)
- Throttle fail-closed via DB: 2 tests proving DB path blocks on 6th attempt and writes hashed rows (4.4)
- Enrollment authorization: self-enroll, cross-enroll denied, owner enroll (4.5)
- Grade isolation: STUDENT list/retrieve for attempts and submissions — own only, 404 on others (4.6)
- Payment isolation: STUDENT list sees only own, TEAM_MEMBER without key denied (4.7)

Test run: **36 tests, 0 failures, 0 errors.**

## Round 3

### 3.1 — Added COURSE to LessonParentType enum + CHECK constraint

**Files:** `apps/core/enums.py`, `apps/content/migrations/0002_lesson_parent_type_check.py`

`LessonParentType` was missing the `COURSE` value, so lessons whose parent is a Course could not be created. Additionally, there was no database-level constraint preventing invalid `parent_type` values.

**Fix:**
- Added `COURSE = "COURSE", "Course"` to `LessonParentType` in `apps/core/enums.py`.
- Migration `0002` AlterField to include all three choices, then AddConstraint with a `CheckConstraint(condition=Q(parent_type__in=["COURSE","WEEK","SECTION"]))` named `lesson_parent_type_valid`.
- Used `condition=` (Django 6.1 rename from `check=`).

---

### 3.2 — Narrowed enrollment GET queryset by caller role

**Files:** `apps/enrollment/views.py`

`EnrollmentListCreateView.get` and `EnrollmentDetailView._get` returned all workspace enrollments to every member, enabling IDOR.

**Fix:**
- STUDENT callers see only their own enrollments (`student_id=request.user.id`).
- PARENT callers see only their linked children's enrollments (via `ParentStudentLink`, `unlinked_at__isnull=True`).
- Staff/owner callers see all enrollments.
- `EnrollmentDetailView._get` raises 404 (not 403) for rows outside the caller's scope.

---

### 3.3 — Fixed IsParentOfStudent field names

**Files:** `apps/core/permissions.py`

`IsParentOfStudent.has_object_permission()` used wrong field names (`parent_user`, `student_user_id`) that don't exist on `ParentStudentLink`, and omitted the `unlinked_at__isnull=True` filter, allowing unlinked parents to pass the check.

**Fix:**
- `parent_user=request.user` → `parent_id=request.user.id`
- `student_user_id=student_id` → `student_id=student_id`
- Added `unlinked_at__isnull=True`

---

### 3.4 — Enrollment POST delegates to enroll() service; fixed MAX_STUDENTS count

**Files:** `apps/enrollment/views.py`, `apps/enrollment/services/eligibility.py`

`EnrollmentListCreateView.post` was calling `Enrollment.objects.create()` directly, bypassing duplicate-enrollment detection and seat-limit checks in `enroll()`. The seat-limit check also counted `WorkspaceMembership` rows instead of active enrollments.

**Fix:**
- `post()` now imports and calls `apps.enrollment.services.eligibility.enroll()`.
- `enroll()` counts `Enrollment.objects.filter(workspace_id=…, status="ACTIVE")` for the seat limit (not membership rows).

---

### 3.5 — WorkspacePermission: is_owner bypasses allowed_roles check

**Files:** `apps/core/permissions.py`

Workspace owners whose membership record stores `role="OWNER"` (a non-standard value) were denied by the `allowed_roles` check at every endpoint, since `"OWNER"` is not in `ALL_MEMBERS`.

**Fix:** Added `if not membership.is_owner: return False` inside the `allowed_roles` branch so owners bypass the role-string check, consistent with the existing bypass for `required_permission_key`.
