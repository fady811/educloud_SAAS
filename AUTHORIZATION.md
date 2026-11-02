# Authorization Matrix

All workspace endpoints are protected by `WorkspacePermission` (inherits from `IsWorkspaceMember`).  
Super-admins bypass all role/permission-key checks.  
Workspace owners (`is_owner=True`) bypass `required_permission_key` checks.

### `allow_roles_without_key`

A rule may include `allow_roles_without_key: frozenset[str]` to let specific roles (e.g. STUDENT, PARENT) access the endpoint without holding the `required_permission_key`. Roles NOT in this set still require the key. Used when students/parents need read access to their own data.

Example:
```python
"GET": {
    "required_permission_key": PermissionKey.PAYMENT_VIEW,
    "allow_roles_without_key": frozenset(["STUDENT", "PARENT"]),
}
```
TEACHER/TEAM_MEMBER still need `PAYMENT_VIEW`; STUDENT/PARENT pass (narrowed by queryset).

## Role Constants

| Constant | Members |
|----------|---------|
| `ALL_MEMBERS` | TEACHER, TEAM_MEMBER, STUDENT, PARENT |
| `STAFF_ONLY` | TEACHER, TEAM_MEMBER |
| `NON_PARENT` | TEACHER, TEAM_MEMBER, STUDENT |
| `STUDENT_ONLY` | STUDENT |
| `PARENT_ONLY` | PARENT |

## Permission Keys

Defined in `apps.accounts.enums.PermissionKey`:
`STUDENT_EDIT`, `CONTENT_CREATE`, `CONTENT_EDIT`, `GROUP_CREATE`, `GROUP_EDIT`, `GROUP_ASSIGN`,
`ASSESSMENT_CREATE`, `ASSESSMENT_EDIT`, `PAYMENT_VIEW`, `PAYMENT_CONFIRM`, `PAYMENT_REJECT`,
`ATTENDANCE_RECORD`, `ATTENDANCE_VIEW_REPORTS`, `REPORTS_VIEW`, `COMM_ANNOUNCEMENTS`, `COMM_DMS`

## Endpoint Matrix

### Content (`apps.content`)

| Endpoint | GET | POST | PATCH/PUT | DELETE |
|----------|-----|------|-----------|--------|
| `/content/subjects/` | ALL_MEMBERS | CONTENT_CREATE | — | — |
| `/content/subjects/{id}/` | ALL_MEMBERS | — | CONTENT_EDIT | owner_only |
| `/content/courses/` | ALL_MEMBERS (STUDENT/PARENT see only PUBLISHED) | CONTENT_CREATE | — | — |
| `/content/courses/{id}/` | ALL_MEMBERS | — | CONTENT_EDIT | owner_only |
| `/content/lessons/` | ALL_MEMBERS (STUDENT/PARENT gated by course.visibility) | CONTENT_CREATE | — | — |
| `/content/lessons/{id}/` | ALL_MEMBERS | — | CONTENT_EDIT | owner_only |

### Groups (`apps.groups`)

| Endpoint | GET | POST | PATCH | DELETE |
|----------|-----|------|-------|--------|
| `/groups/` | ALL_MEMBERS | GROUP_CREATE | — | — |
| `/groups/{id}/` | ALL_MEMBERS | — | GROUP_EDIT | owner_only |
| `/groups/{id}/members/` | — | GROUP_ASSIGN | — | GROUP_ASSIGN |
| `/groups/{id}/sessions/` | ALL_MEMBERS | ATTENDANCE_RECORD | — | — |
| `/groups/{id}/sessions/{sid}/attendance/` | — | ATTENDANCE_RECORD | — | — |

### Assessments (`apps.assessments`)

| Endpoint | GET | POST | PUT/PATCH | DELETE |
|----------|-----|------|-----------|--------|
| `/assessments/exams/` | ALL_MEMBERS | ASSESSMENT_CREATE | — | — |
| `/assessments/exams/{id}/` | ALL_MEMBERS | — | ASSESSMENT_EDIT | owner_only |
| `/assessments/questions/` | ALL_MEMBERS | ASSESSMENT_CREATE | — | — |
| `/assessments/questions/{id}/` | ALL_MEMBERS | — | ASSESSMENT_EDIT | owner_only |
| `/assessments/assignments/` | ALL_MEMBERS | ASSESSMENT_CREATE | — | — |
| `/assessments/assignments/{id}/` | ALL_MEMBERS | — | ASSESSMENT_EDIT | owner_only |
| `/exam-attempts/` | ALL_MEMBERS (STUDENT/PARENT: own only, queryset narrowed) | STUDENT_ONLY | — | — |
| `/exam-attempts/{id}/submit` | — | STUDENT_ONLY (own only) | — | — |
| `/assignment-submissions/` | ALL_MEMBERS (STUDENT/PARENT: own only, queryset narrowed) | STUDENT_ONLY | — | — |

### Enrollment (`apps.enrollment`)

| Endpoint | GET | POST | DELETE |
|----------|-----|------|--------|
| `/enrollment/enrollments/` | ALL_MEMBERS | ALL_MEMBERS (STUDENT=self only; else STUDENT_EDIT) | — |
| `/enrollment/enrollments/{id}/` | ALL_MEMBERS | — | STUDENT_EDIT |

Enrollment POST also verifies: target must be a STUDENT member; MAX_STUDENTS limit enforced.

### Communication (`apps.communication`)

| Endpoint | GET | POST | PUT/PATCH | DELETE |
|----------|-----|------|-----------|--------|
| `/comm/announcements/` | ALL_MEMBERS | COMM_ANNOUNCEMENTS | COMM_ANNOUNCEMENTS | COMM_ANNOUNCEMENTS |
| `/comm/conversations/` | ALL_MEMBERS | NON_PARENT (TEAM_MEMBER also needs COMM_DMS) | — | — |
| `/comm/conversations/{id}/messages/` | ALL_MEMBERS | NON_PARENT (TEAM_MEMBER also needs COMM_DMS) | — | — |

### Payments (`apps.payments`)

| Endpoint | GET | POST | PUT/PATCH | DELETE |
|----------|-----|------|-----------|--------|
| `/student-payments/` | PAYMENT_VIEW (STUDENT/PARENT bypass key; queryset narrowed to own/children) | ALL_MEMBERS (STUDENT=self only) | — | owner_only |
| `/payments/student-payments/{id}/submit-proof` | — | owner (own payment only) | — | — |
| `/payments/student-payments/{id}/approve` | — | PAYMENT_CONFIRM | — | — |
| `/payments/student-payments/{id}/reject` | — | PAYMENT_REJECT | — | — |
| `/payments/methods/` | ALL_MEMBERS | owner_only | owner_only | owner_only |

### Reports (`apps.reports`)

| Endpoint | GET |
|----------|-----|
| `/reports/attendance/` | ATTENDANCE_VIEW_REPORTS |
| `/reports/payments/` | REPORTS_VIEW |
| `/reports/enrollments/` | REPORTS_VIEW |

### Support (`apps.support`)

| Endpoint | GET | POST | PATCH |
|----------|-----|------|-------|
| `/support/tickets/` | ALL_MEMBERS (own only unless REPORTS_VIEW) | ALL_MEMBERS | — |
| `/support/tickets/{id}/` | ALL_MEMBERS (own only unless REPORTS_VIEW) | — | ALL_MEMBERS (own only unless REPORTS_VIEW) |
| `/support/tickets/{id}/messages/` | — | ALL_MEMBERS (own ticket unless REPORTS_VIEW) | — |

### Parents (`apps.parents`)

| Endpoint | GET | POST | DELETE |
|----------|-----|------|--------|
| `/parents/links/` | — | STUDENT_EDIT | STUDENT_EDIT |
| `/parents/students/` | PARENT_ONLY | — | — |

### Files (`apps.files`)

| Endpoint | GET | POST | DELETE |
|----------|-----|------|--------|
| `/files/upload-request/` | — | ALL_MEMBERS | — |
| `/files/{id}/` | ALL_MEMBERS | — | ALL_MEMBERS (uploader or owner) |

## Billing (`apps.billing`)

Billing endpoints use `IsWorkspaceOwner` (not `WorkspacePermission`).
Super-admin actions (`approve`, `reject`) use `IsSuperAdmin`.

## Round 3 additions

### Students (`apps.accounts` — student sub-routes)

| Endpoint | GET | POST | PATCH | DELETE |
|----------|-----|------|-------|--------|
| `/students/` | STUDENT_VIEW | STUDENT_CREATE | — | — |
| `/students/{id}/` | STUDENT_VIEW | — | STUDENT_EDIT | STUDENT_DEACTIVATE |
| `/students/import/` | — | STUDENT_CREATE | — | — |
| `/students/import/{id}/` | STUDENT_VIEW | — | — | — |

### Auth — verification & password reset (`apps.accounts`)

All endpoints below use `AllowAny` (unauthenticated by design):

| Endpoint | POST |
|----------|------|
| `/auth/verify/` | Verify email/phone token (sets `email_verified_at` or `phone_verified_at`) |
| `/auth/verify/resend/` | Re-issue a verification token |
| `/auth/password-reset/` | Request password reset link |
| `/auth/password-reset/confirm/` | Apply new password; revokes all active sessions |

### Lesson content (`apps.content`)

| Endpoint | GET |
|----------|-----|
| `/lessons/{id}/content/` | ALL_MEMBERS — STUDENT/PARENT additionally checked via `lesson_accessible()` |

STUDENT and PARENT callers are subject to the 7-step access check:
1. Lesson exists and is not archived
2. Parent course is PUBLISHED and not archived
3. Free-preview lesson → allowed without enrollment
4. Active enrollment in the course exists
5. Enrollment is not expired/cancelled
6. `StudentCourseAccess` row exists, is not revoked, and has not expired
7. Workspace status is ACTIVE or GRACE_PERIOD

PARENT callers use their first linked child's `student_id` for the check.
