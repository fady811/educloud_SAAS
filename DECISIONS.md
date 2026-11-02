# Architecture Decisions

## Round 3

### D-01: StudentCourseAccess as lesson-access source of truth

**Decision:** `StudentCourseAccess` (not `Enrollment` alone) is the authoritative check for whether a student may view lesson content.

**Context:** A student may be enrolled in a course but have a revoked or expired per-student access grant (e.g. their subscription lapsed while others continue). The enrollment record alone cannot express this granularity.

**Consequence:** `lesson_accessible()` in `apps/enrollment/services/access.py` requires **both** an active enrollment **and** a valid `StudentCourseAccess` row (not revoked, not expired). Removing a `StudentCourseAccess` row blocks content access without cancelling the enrollment.

---

### D-02: MAX_STUDENTS limit counts active Enrollment rows, not WorkspaceMembership rows

**Decision:** The `LimitKey.MAX_STUDENTS` seat check in `enroll()` counts `Enrollment.objects.filter(workspace_id=…, status="ACTIVE")`, not `WorkspaceMembership` rows with `role=STUDENT`.

**Context:** A workspace may have many student members who are not currently enrolled in anything, or students from a previous billing cycle whose enrollments have been cancelled. The billing limit is about concurrent active enrollments (seats in use), not total student head-count.

**Consequence:** A student can be a member of the workspace without consuming a seat. A seat is consumed only when an active enrollment exists.

---

### D-03: WorkspacePermission allowed_roles bypass for is_owner=True

**Decision:** A workspace member with `is_owner=True` bypasses the `allowed_roles` check in `WorkspacePermission`, in addition to the existing `required_permission_key` bypass.

**Context:** The test infrastructure and some legacy paths create the workspace owner with `role="OWNER"` (a non-standard role string not in `ALL_MEMBERS`). Owners must be able to reach any endpoint that any member role can reach.

**Consequence:** `membership.is_owner=True` implies full access to any `allowed_roles`-gated endpoint. The `owner_only` rule remains a stricter gate that still blocks non-owners.
