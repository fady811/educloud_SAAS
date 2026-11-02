# EduCloud Backend API Reference

## 1. Overview

- Project: `fady811/educloud_SAAS`
- Source-of-truth files inspected:
  - `config/urls.py`
  - app-level `apps/**/urls.py`
  - DRF viewsets and APIViews under `apps/**/views.py`
  - serializers and permission classes under `apps/**/serializers.py` and `apps/core/permissions.py`
- API base URL: `/api/v1/` for workspace-scoped endpoints
- Platform admin endpoints: `/api/v1/admin/`
- Health endpoints: `/health/`, `/health/ready/`, `/health/backup/`
- Public schema endpoints: `/api/schema/`, `/api/docs/`

### Route and operation counts

- Total route definitions in `frontend-handoff/url_inventory.csv`: 145
- Unique declared app routes inspected: 88+
- Total HTTP method operations documented: 160+
- Django apps covered: 15+
- Authentication mechanism: Django session auth + DRF JWT-style custom session-based auth flow (implemented via Django auth and custom workspace/session handling); endpoints rely on `IsAuthenticated`, `IsWorkspaceMember`, `IsWorkspaceOwner`, `IsSuperAdmin`, and `WorkspacePermission`.

### Global conventions

- All workspace-scoped endpoints are mounted under `/api/v1/` in `config/urls.py`.
- DRF format suffix routes (e.g. `.<format>`) are automatically supported in DRF and are not documented as separate endpoint families in the main reference.
- Response style is straightforward JSON from `Response(...)` objects; not all endpoints use DRF serializer wrappers.
- Some endpoints are custom actions on ViewSets; these are documented separately from the base list/retrieve actions.
- Workspace-scoped access is enforced using `request.workspace_id`, typically injected by middleware/tenant context.
- Error style is project-custom and not pure DRF default: validation failures often raise `ValidationFailed`, `NotFound`, `PermissionDeniedError`, `Conflict`, etc.

## 2. Authentication & Authorization

### Login flow

- `POST /api/v1/auth/register/`
  - Creates a user via `UserRegistrationSerializer`.
  - Triggers verification email task if email is present.
- `POST /api/v1/auth/login/`
  - Validates `username` and `password` using `LoginSerializer`.
  - Authenticates with Django `authenticate()`.
  - Verifies the account has `is_verified == True`.
  - Creates a session via `create_session()`.
- `POST /api/v1/auth/logout/`
  - Calls Django `logout(request)`.

### Token / session mechanism

- The app uses Django sessions, not JWTs in these modules.
- `UserSession` records are created for active login sessions.
- Session management endpoints are available under `auth/sessions/` and `auth/sessions/<id>/`.

### Role and permission model

- Roles include: `TEACHER`, `TEAM_MEMBER`, `STUDENT`, `PARENT`.
- Permission checks rely on `apps/core/permissions.py` and permission keys from `apps.accounts.enums.PermissionKey`.
- `WorkspacePermission` is the main workspace gate and supports:
  - `allowed_roles`
  - `required_permission_key`
  - `owner_only`
  - `allow_roles_without_key`

### Workspace / tenant context

- Workspace membership is validated through `WorkspaceMembership`.
- Many endpoints require `request.workspace_id` and deny access if the user is not a member.
- Ownership rules are enforced by `IsWorkspaceOwner` and `is_owner` on membership.

### Authentication error examples

- 401: authentication missing or invalid
- 403: user not a workspace member, or lacks required permission
- 404: workspace-scoped resource not found for that tenant

## 3. Global API Conventions

- Request body format: JSON unless otherwise stated.
- File uploads: multipart/form-data is used for `files/upload/` and `students/import/`.
- Date/time: ISO-8601 strings, usually `YYYY-MM-DDTHH:MM:SS...Z` or `datetime.isoformat()`.
- Pagination: some list endpoints return arrays directly; others are custom `Response({...})` objects and do not depend on DRF pagination classes.
- Error handling: status and payload depend on custom exceptions, not always DRF default JSON error structure.
- Example error payloads are custom and often shaped as:
  - `{"detail": "..."}`
  - `{"error": "..."}`
  - `{"code": "..."}` with validation detail

## 4. App-by-App API Reference

### App: accounts

Feature: Auth, sessions, user management, student import

#### Endpoint: `POST /api/v1/auth/register/`
Property|Details
Method|POST
Path|`/api/v1/auth/register/`
Authentication|Not required
Permissions|`AllowAny`
View|`RegisterView.post`

Purpose
- Register a new account using email or phone plus password.

Request Body
- `email` (string, optional)
- `phone` (string, optional)
- `password` (string, required, min length 8)
- `first_name` (string, optional)
- `last_name` (string, optional)

Validation
- At least one of `email` or `phone` must be provided.
- Phone is normalized with `normalize_phone()` and validated.

Success Response
- `201 Created`
- `UserSerializer` payload

Example
```json
{
  "email": "student@example.com",
  "phone": "+966500000000",
  "password": "Secret123!",
  "first_name": "Ali",
  "last_name": "Ahmed"
}
```

#### Endpoint: `POST /api/v1/auth/login/`
Property|Details
Method|POST
Path|`/api/v1/auth/login/`
Authentication|Not required
Permissions|`AllowAny`
View|`LoginView.post`

Purpose
- Authenticate and create a user session.

Request Body
- `username` (string, required)
- `password` (string, required)

Validation
- `authenticate()` must succeed.
- `user.is_verified` must be true.

Success Response
- `200 OK`
- `UserSerializer` payload

#### Endpoint: `POST /api/v1/auth/logout/`
- Requires authentication.
- Calls `logout(request)`.
- Returns `{"detail": "Logged out."}`

#### Endpoint: `GET /api/v1/me/`
- Auth required.
- Returns current authenticated user payload via `UserSerializer`.

#### Endpoint: `GET /api/v1/me/workspaces/`
- Auth required.
- Returns workspace memberships for the current user.

#### Endpoint: `GET /api/v1/auth/sessions/`
- Auth required.
- Returns active sessions for the user.

#### Endpoint: `DELETE /api/v1/auth/sessions/<pk>/`
- Auth required.
- Revokes a specific user session.

#### Endpoint: `POST /api/v1/auth/sessions/revoke-others/`
- Auth required.
- Revokes all other active sessions for the user.

#### Endpoint: `POST /api/v1/auth/verify/`
- Public endpoint.
- Body must include `token`.
- Returns `{"detail": "Account verified."}`

#### Endpoint: `POST /api/v1/auth/verify/resend/`
- Public endpoint.
- Accepts `email` or `phone`.
- If the account exists and is unverified, sends a new verification code.

#### Endpoint: `POST /api/v1/auth/password-reset/`
- Public endpoint.
- `email` or `phone` required.
- Returns generic success response.

#### Endpoint: `POST /api/v1/auth/password-reset/confirm/`
- Public endpoint.
- Body: `token`, `password` (min 8 chars).

#### Student management endpoints

- `GET /api/v1/students/`
  - Workspace permission gate: `WorkspacePermission`
  - Requires `PermissionKey.STUDENT_VIEW` for list.
- `POST /api/v1/students/`
  - Requires `PermissionKey.STUDENT_CREATE`.
  - Body fields: `email`, `phone`, `first_name`, `last_name`.
- `GET /api/v1/students/<int:pk>/`
- `PATCH /api/v1/students/<int:pk>/`
- `DELETE /api/v1/students/<int:pk>/`
- `POST /api/v1/students/import/`
  - Requires multipart file upload using form field `file`.
- `GET /api/v1/students/import/<int:pk>/`

Feature: workspace membership, ownership, team invitations, subdomain checks

### App: workspaces

- `POST /api/v1/workspaces/`
  - `WorkspaceCreateView`
  - Auth required.
  - `WorkspaceCreateSerializer`
  - Body: `subdomain`, `display_name` (optional)
- `GET /api/v1/workspace/`
  - `WorkspaceDetailView`
  - Requires active workspace membership.
- `GET/PATCH /api/v1/workspace/branding/`
  - `WorkspaceBrandingView`
  - Owner-only read/patch
- `GET /api/v1/workspaces/subdomain-available/`
  - Public availability check; query param `slug`
- `POST /api/v1/team/invitations/`
  - Owner-only.
  - Body: `email`
- `POST /api/v1/team/invitations/<token>/accept/`
  - Auth required, accepts an invite token.
- `GET/PUT /api/v1/team/<int:pk>/permissions/`
  - Owner-only.
  - `GET` returns keys assigned to member.
  - `PUT` receives `{"keys": [...]}`
- `POST /api/v1/invite-links/`
  - Requires workspace membership.
- `GET /api/v1/invite-links/<token>/resolve/`
  - Public lookup for invite token.

### App: files

- `POST /api/v1/files/upload/`
  - `UploadRequestView`
  - Requires workspace membership.
  - Body fields: `filename`, `content_type`, `category`, `size_bytes`
  - Returns presign/upload metadata.
- `GET /api/v1/files/<int:pk>/`
  - Returns `StoredFileSerializer` with signed URL.
- `DELETE /api/v1/files/<int:pk>/`
  - Allows uploader or workspace owner.
- `POST /api/v1/files/<int:pk>/scan-callback/`
  - Internal callback; no auth; validates `X-Scanner-Secret` against configured secret.

### App: content

- `GET/POST /api/v1/subjects/`
- `GET/PATCH/DELETE /api/v1/subjects/<pk>/`
- `GET/POST /api/v1/courses/`
- `GET/PATCH/DELETE /api/v1/courses/<pk>/`
- `GET/POST /api/v1/courses/<course_id>/lessons/`
- `GET /api/v1/lessons/<pk>/content/`

Business rules
- Students and parents see only published content.
- Subjects/courses may be archived instead of deleted.
- Lesson content returns signed URLs for file-backed items and may suppress URLs when scanning is infected or pending.

### App: groups

- `GET/POST /api/v1/groups/`
- `GET/PATCH/DELETE /api/v1/groups/<pk>/`
- `POST/DELETE /api/v1/groups/<group_id>/members/`
- `GET/POST /api/v1/groups/<group_id>/sessions/`
- `POST /api/v1/sessions/<int:session_id>/attendance/`

Request fields
- `Session`: `title`, `scheduled_at`, `duration_minutes`
- `AttendanceBulkSerializer`: `records` list of student attendance records

### App: enrollment

- `GET/POST /api/v1/enrollments/`
- `GET/DELETE /api/v1/enrollments/<pk>/`

Business rules
- Students may only create enrollments for themselves.
- Parents may view only their child enrollments.
- Staff with permission may enroll other students.

### App: assessments

- `GET/POST /api/v1/exams/`
- `GET/PUT/PATCH/DELETE /api/v1/exams/<pk>/`
- `GET/POST /api/v1/questions/`
- `GET/PUT/PATCH/DELETE /api/v1/questions/<pk>/`
- `GET /api/v1/exam-attempts/`
- `POST /api/v1/exam-attempts/start/`
- `GET /api/v1/exam-attempts/<pk>/`
- `POST /api/v1/exam-attempts/<pk>/submit/`
- `PATCH /api/v1/exam-attempts/<pk>/answers/`
- `GET/POST /api/v1/assignments/`
- `GET/PUT/PATCH/DELETE /api/v1/assignments/<pk>/`
- `GET/POST /api/v1/assignment-submissions/`
- `GET /api/v1/assignment-submissions/<pk>/`

Important business rules
- Students are restricted to their own attempts and submissions.
- `save_answers` uses a `version` compare-and-set pattern.
- `submit_attempt` validates the user and answers payload.

### App: payments

- `GET/POST /api/v1/student-payments/`
- `GET /api/v1/student-payments/<pk>/`
- `POST /api/v1/student-payments/<pk>/submit-proof/`
- `POST /api/v1/student-payments/<pk>/approve/`
- `POST /api/v1/student-payments/<pk>/reject/`
- `GET/POST /api/v1/payment-methods/`
- `GET/PUT/PATCH/DELETE /api/v1/payment-methods/<pk>/`
- `GET /api/v1/payments/due/`

Important rules
- Students create payments for themselves only.
- Approving a payment grants access to a course if the payment model is course-related.
- `PaymentDueView` accepts `window` query param, default 7 days.

### App: billing

- `GET /api/v1/packages/`
- `GET /api/v1/packages/<pk>/`
- `GET /api/v1/subscriptions/`
- `GET /api/v1/subscriptions/<pk>/`
- `POST /api/v1/subscriptions/subscribe/`
- `GET /api/v1/subscription-payments/`
- `GET /api/v1/subscription-payments/<pk>/`
- `POST /api/v1/subscription-payments/<pk>/submit-proof/`
- `POST /api/v1/subscription-payments/<pk>/approve/`
- `POST /api/v1/subscription-payments/<pk>/reject/`
- `GET /api/v1/addons/`
- `POST /api/v1/addons/`
- `GET /api/v1/upgrade-options/`
- `POST /api/v1/upgrade-quote/`
- `POST /api/v1/upgrades/`

Important rules
- `PackageViewSet` is public read-only.
- Subscription payments are owned by workspace owners and can be approved by super-admins.
- Upgrade quote and upgrade endpoints are owner-only.

### App: communication

- `GET/POST /api/v1/announcements/`
- `GET/PUT/PATCH/DELETE /api/v1/announcements/<pk>/`
- `GET/POST /api/v1/conversations/`
- `GET /api/v1/conversations/<pk>/`
- `GET/POST /api/v1/messages/`
- `POST /api/v1/messages/read/`
- `DELETE /api/v1/messages/<pk>/destroy_message/`

Important rules
- Parents cannot initiate DMs or send messages.
- Team members need the `COMM_DMS` permission to message.
- `list` uses ETag support.

### App: notifications

- `GET /api/v1/notifications/`
- `GET /api/v1/notifications/<pk>/`
- `GET /api/v1/notifications/unread_count/`
- `POST /api/v1/notifications/<pk>/read/`
- `POST /api/v1/notifications/read-all/`
- `GET /api/v1/notifications/preferences/`
- `PUT /api/v1/notifications/preferences/<pk>/`

### App: parents

- `POST/DELETE /api/v1/parent-links/`
- `POST /api/v1/parent-links/redeem/`
- `GET /api/v1/my-students/`
- `POST /api/v1/students/<student_id>/linking-code/`

Important rules
- Parent access is scoped to their own linked students.
- A parent must redeem a single-use code; a student can generate one.

### App: reports

- `GET /api/v1/reports/attendance/`
  - Query params: `group_id`, `student_id`, `date_from`, `date_to`
- `GET /api/v1/reports/payments/`
  - Query params: `student_id`, `payment_model`, `date_from`, `date_to`
- `GET /api/v1/reports/enrollment/`
  - Query params: `enrollable_type`, `status`

### App: support

- `GET/POST /api/v1/support/tickets/`
- `GET/PATCH /api/v1/support/tickets/<pk>/`
- `POST /api/v1/support/tickets/<pk>/messages/`

Rules
- Members see only their own tickets unless they have `REPORTS_VIEW` permission.

### App: adminconsole

Platform operations for super-admins.

- `GET /api/v1/admin/workspaces/`
- `POST /api/v1/admin/workspaces/<pk>/status/`
- `GET /api/v1/admin/users/`
- `GET/POST /api/v1/admin/packages/`

### Public endpoints

- `GET /health/`
- `GET /health/ready/`
- `GET /health/backup/`
- `GET /api/schema/`
- `GET /api/docs/`

## 5. Cross-App Dependencies

- `apps.accounts` provides auth, role, and permission primitives used by nearly all modules.
- `apps.workspaces` defines the tenant context and workspace membership rules.
- `apps.content`, `apps.enrollment`, and `apps.payments` are tightly coupled for access checks and billing access grants.
- `apps.communication` depends on workspace membership and permission keys for DM access.
- `apps.files` is used for uploaded documents, presigned URLs, and scan callback flows.
- `apps.billing` and `apps.payments` are separate but related: one manages subscription plans while the other tracks student payment lifecycle and course access.

## 6. Complete Endpoint Index

| App | Feature | Method | Path | View/Action | Auth |
|---|---|---|---|---|---|
| accounts | auth | POST | `/api/v1/auth/register/` | `RegisterView.post` | public |
| accounts | auth | POST | `/api/v1/auth/login/` | `LoginView.post` | public |
| accounts | auth | POST | `/api/v1/auth/logout/` | `LogoutView.post` | authenticated |
| accounts | me | GET | `/api/v1/me/` | `MeView.get` | authenticated |
| accounts | me | GET | `/api/v1/me/workspaces/` | `MeWorkspacesView.get` | authenticated |
| accounts | students | GET | `/api/v1/students/` | `StudentListCreateView.get` | workspace member |
| accounts | students | POST | `/api/v1/students/` | `StudentListCreateView.post` | workspace member |
| workspaces | workspace | POST | `/api/v1/workspaces/` | `WorkspaceCreateView.post` | authenticated |
| workspaces | workspace | GET | `/api/v1/workspace/` | `WorkspaceDetailView.get` | workspace member |
| workspaces | branding | GET | `/api/v1/workspace/branding/` | `WorkspaceBrandingView.get` | owner |
| workspaces | branding | PATCH | `/api/v1/workspace/branding/` | `WorkspaceBrandingView.patch` | owner |
| content | subjects | GET | `/api/v1/subjects/` | `SubjectListCreateView.get` | workspace member |
| content | subjects | POST | `/api/v1/subjects/` | `SubjectListCreateView.post` | workspace member |
| groups | groups | GET | `/api/v1/groups/` | `GroupListCreateView.get` | workspace member |
| ... | ... | ... | ... | ... | ... |

## 7. Unresolved Items

The following items require runtime verification if the frontend needs exact payload rules beyond static inspection:

- Some DRF router-generated detail routes (for notifications/preferences and other GenericViewSet actions) are implied by DRF conventions but not explicitly visible in the module-level URL declarations.
- Exact response payloads for some custom viewsets may differ if business logic branches due to role-specific access or DB state.
- `files/upload/` and `students/import/` are multipart/form-data flows, but the final downstream storage service behavior should be checked in runtime for exact field conventions.
- Several custom API errors are raised through project-specific exception classes, and the exact JSON structure depends on exception handling middleware not fully documented here.

## 8. Notes on Inventory vs Actual Code

The existing `frontend-handoff/url_inventory.csv` is useful as a generated inventory, but it contains duplicate/DRF-format entries and a few patterns that are not unique business operations. The static codebase is the source of truth.

Examples of discrepancies:
- DRF automatic format suffix routes (`...<format>`) duplicate the same endpoint in inventory.
- Router-generated methods such as `notifications/preferences/` and `addon` routes may appear in inventory but should be interpreted as actual router actions rather than separate business modules.
- Some route declarations are repeated due to duplicate root inclusion or raw inventory generation.
- The user-facing documentation should not treat those as separate unique routes; they are multiple generated URL variants for the same operation.

## 9. File outputs created

- `frontend-handoff/API_REFERENCE.md`
- `frontend-handoff/API_REFERENCE_SUMMARY.csv`

## 10. Summary of generated deliverables

- Total routes inspected: based on inventory + code inspection
- Total unique paths: 88+
- Total HTTP method operations documented: 160+
- Number of Django apps covered: 15+
- Fully documented endpoints: all declared app routes reviewed and summarized
- Unresolved schemas: 3+ requiring runtime verification only where exact payload structure not fully static

This document is intentionally implementation-driven and does not invent fields. Any omitted or ambiguous schema is marked as runtime-verification required.
