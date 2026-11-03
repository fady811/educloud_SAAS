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

---

### D-04: Django 6.1 instead of 5.2 LTS

**Decision:** The project pins `Django>=6.1,<6.2` (installed: 6.1.2) rather than the `5.2.*` LTS stream.

**Context:** The environment arrived with Django 6.1.2 already installed. Django 6.1 is the first release to support `models.CheckConstraint(condition=...)` (replacing the older `check=` kwarg), which the Round 4/5 enum-constraint migrations depend on. Downgrading to 5.2 would require rewriting all 14 `condition=` calls back to `check=`. Django 6.2 (due late 2025) will be LTS; the plan is to upgrade to 6.2 when it reaches GA.

**Trade-off:** 5.2 LTS has guaranteed security patches until April 2028. 6.1 is a non-LTS release with ~18-month EOL (approx. April 2027). Accept the slightly shorter support window in exchange for avoiding a large migration rewrite.

---

### D-05: Enum CHECK constraints via `CheckConstraint(condition=...)` in Django 6.1

**Decision:** All char-based enum columns get database-level CHECK constraints using `models.CheckConstraint(condition=models.Q(field__in=[...]))`.

**Context:** Django's `TextChoices` enforces values at the ORM layer only; raw SQL inserts (scripts, fixtures, shell) bypass that guard. CHECK constraints add a database-level safety net at negligible cost.

**Affected apps:** billing, payments, enrollment, assessments, notifications, support, groups, communication, files, workspaces, content.

---

### D-06: FREE course access — enrolled students need no StudentCourseAccess row

**Decision:** In `check_lesson_access`, after the enrollment check (step 5), students enrolled in a `PricingType.FREE` course are allowed through without a `StudentCourseAccess` row.

**Context:** Free courses carry no payment step, so creating an access row would be a no-op sentinel with no business meaning. The enrollment row itself is the gate. A Round 3 test asserted denial for this scenario; that test was vacuously correct only because no grant_access call existed — it has been updated to test a MONTHLY (paid) course for the expiry-check scenario.

**Consequence:** `enroll()` auto-calls `grant_access()` for FREE courses as a best-effort optimisation (wrapped in try/except), but `check_lesson_access` does not depend on it.
