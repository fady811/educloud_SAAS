"""
End-to-end API tests — all 12 required scenarios plus additional checks.
Uses Django TestClient through the full middleware/auth/permission stack.
Workspace context is resolved via subdomain: <slug>.educloud.test
"""
from __future__ import annotations

import json

from django.test import TestCase, Client, override_settings
from django.utils import timezone

BASE_DOMAIN = "educloud.test"
PLATFORM_HOST = BASE_DOMAIN


def _ws_host(subdomain: str) -> str:
    return f"{subdomain}.{BASE_DOMAIN}"


_ip_counter = 0


class E2EBase(TestCase):

    def setUp(self):
        super().setUp()
        # Clear login-throttle Redis keys so each test class starts fresh
        from django.core.cache import cache
        cache.clear()

    def _unique_ip(self):
        global _ip_counter
        _ip_counter += 1
        return f"10.0.{(_ip_counter >> 8) & 0xFF}.{_ip_counter & 0xFF}"

    def _post(self, client, path, data, host=PLATFORM_HOST):
        return client.post(
            f"/api/v1/{path}",
            data=json.dumps(data),
            content_type="application/json",
            HTTP_HOST=host,
            SERVER_NAME=host.split(":")[0],
            REMOTE_ADDR=self._unique_ip(),
        )

    def _get(self, client, path, host=PLATFORM_HOST, qs=""):
        return client.get(
            f"/api/v1/{path}{qs}",
            HTTP_HOST=host,
            SERVER_NAME=host.split(":")[0],
        )

    def _login(self, client, email=None, phone=None, password="Pass1234!", host=PLATFORM_HOST):
        return self._post(client, "auth/login/", {"username": email or phone, "password": password}, host=host)

    def _make_verified_user(self, email=None, phone=None, password="Pass1234!", is_super_admin=False):
        from apps.accounts.services.registration import register_user
        u, _ = register_user(email=email, phone=phone, password=password)
        if email:
            u.email_verified_at = timezone.now()
        else:
            u.phone_verified_at = timezone.now()
        if is_super_admin:
            u.is_super_admin = True
        u.save()
        return u

    def _make_workspace(self, subdomain, owner):
        from apps.workspaces.models import Workspace, WorkspaceMembership
        ws = Workspace.objects.create(
            subdomain=subdomain,
            status="SETUP",
            settings_json={"display_name": subdomain},
        )
        WorkspaceMembership.objects.create(user=owner, workspace=ws, role="TEACHER", is_owner=True)
        return ws

    def _activate_workspace(self, ws):
        from apps.workspaces.services.lifecycle import transition
        from apps.core.enums import WorkspaceStatus, ActorType
        for target in (WorkspaceStatus.PENDING_PAYMENT, WorkspaceStatus.PENDING_APPROVAL, WorkspaceStatus.ACTIVE):
            ws.refresh_from_db()
            transition(ws, target, actor_type=ActorType.ADMIN, reason="e2e test setup")
        ws.refresh_from_db()
        return ws

    def _login_client(self, email, password="Pass1234!", host=PLATFORM_HOST):
        c = Client()
        r = self._login(c, email=email, password=password, host=host)
        assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.content[:300]}"
        return c


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class Scenario1_AdminWorkspaceActivation(E2EBase):
    """Scenario 1: Super Admin lists workspaces, creates package, transitions status."""

    def test_super_admin_can_list_workspaces(self):
        self._make_verified_user(email="sadmin1@e2e.test", is_super_admin=True)
        c = self._login_client("sadmin1@e2e.test")
        r = self._get(c, "admin/workspaces/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("results", r.json())

    def test_super_admin_create_package(self):
        self._make_verified_user(email="sadmin2@e2e.test", is_super_admin=True)
        c = self._login_client("sadmin2@e2e.test")
        r = self._post(c, "admin/packages/", {
            "name": "E2E Basic Plan",
            "slug": "e2e-basic-plan",
            "price_egp": "149.00",
            "duration_months": 1,
            "max_students": 50,
        })
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn("id", r.json())

    def test_non_admin_cannot_access_admin_api(self):
        self._make_verified_user(email="regular1@e2e.test")
        c = self._login_client("regular1@e2e.test")
        r = self._get(c, "admin/workspaces/")
        self.assertEqual(r.status_code, 403, r.content)

    def test_unauthenticated_cannot_access_admin_api(self):
        c = Client()
        r = self._get(c, "admin/workspaces/")
        self.assertIn(r.status_code, [401, 403])

    def test_admin_transitions_workspace_status(self):
        self._make_verified_user(email="sadmin3@e2e.test", is_super_admin=True)
        owner = self._make_verified_user(email="ws_owner_s1@e2e.test")
        ws = self._make_workspace("e2e-scenario1-s1", owner)
        c = self._login_client("sadmin3@e2e.test")
        r = self._post(c, f"admin/workspaces/{ws.id}/status/", {
            "status": "PENDING_PAYMENT", "reason": "e2e test"
        })
        self.assertEqual(r.status_code, 200, r.content)
        ws.refresh_from_db()
        self.assertEqual(ws.status, "PENDING_PAYMENT")


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class Scenario2_OwnerAuth(E2EBase):
    """Scenario 2: Workspace owner authenticates and receives session."""

    def test_owner_login_success(self):
        self._make_verified_user(email="owner_auth@e2e.test")
        c = Client()
        r = self._login(c, email="owner_auth@e2e.test")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["email"], "owner_auth@e2e.test")

    def test_login_with_wrong_password_returns_error(self):
        self._make_verified_user(email="owner_wrong@e2e.test")
        c = Client()
        r = self._login(c, email="owner_wrong@e2e.test", password="BADPASS")
        self.assertIn(r.status_code, [400, 401, 422])

    def test_unverified_user_cannot_login(self):
        from apps.accounts.models import User
        u = User(email="unverified@e2e.test", first_name="U", last_name="V")
        u.set_password("Pass1234!")
        u.save()
        c = Client()
        r = self._login(c, email="unverified@e2e.test")
        self.assertIn(r.status_code, [400, 401, 422])

    def test_me_endpoint_requires_auth(self):
        c = Client()
        r = c.get("/api/v1/me/", HTTP_HOST=PLATFORM_HOST)
        self.assertIn(r.status_code, [401, 403])

    def test_me_endpoint_returns_user(self):
        self._make_verified_user(email="me_test@e2e.test")
        c = self._login_client("me_test@e2e.test")
        r = c.get("/api/v1/me/", HTTP_HOST=PLATFORM_HOST)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["email"], "me_test@e2e.test")

    def test_logout_clears_session(self):
        self._make_verified_user(email="logout_test@e2e.test")
        c = self._login_client("logout_test@e2e.test")
        self._post(c, "auth/logout/", {})
        r = c.get("/api/v1/me/", HTTP_HOST=PLATFORM_HOST)
        self.assertIn(r.status_code, [401, 403])


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class Scenario3_ContentCreation(E2EBase):
    """Scenario 3: Owner creates subject, course, lesson via API."""

    def setUp(self):
        super().setUp()
        self.owner = self._make_verified_user(email="owner_content@e2e.test")
        self.ws = self._make_workspace("e2e-content", self.owner)
        self._activate_workspace(self.ws)
        self.host = _ws_host(self.ws.subdomain)
        self.c = self._login_client("owner_content@e2e.test", host=self.host)

    def test_create_subject(self):
        r = self._post(self.c, "subjects/", {"name": "Mathematics"}, host=self.host)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["name"], "Mathematics")

    def test_create_course(self):
        from apps.content.models import Subject
        subj = Subject.objects.create(workspace=self.ws, name="Physics")
        r = self._post(self.c, "courses/", {
            "title": "Physics 101",
            "subject_id": subj.id,
            "visibility": "DRAFT",
        }, host=self.host)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["title"], "Physics 101")

    def test_create_lesson(self):
        from apps.content.models import Subject, Course
        subj = Subject.objects.create(workspace=self.ws, name="Chemistry")
        course = Course.objects.create(workspace=self.ws, title="Chemistry 101", subject=subj)
        r = self._post(self.c, f"courses/{course.id}/lessons/", {
            "title": "Atoms and Molecules", "order": 1,
        }, host=self.host)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["title"], "Atoms and Molecules")

    def test_list_subjects_workspace_scoped(self):
        from apps.content.models import Subject
        Subject.objects.create(workspace=self.ws, name="Biology")
        other_owner = self._make_verified_user(email="other_owner_c@e2e.test")
        other_ws = self._make_workspace("e2e-other-content", other_owner)
        Subject.objects.create(workspace=other_ws, name="History")
        r = self._get(self.c, "subjects/", host=self.host)
        self.assertEqual(r.status_code, 200)
        names = [s["name"] for s in r.json()]
        self.assertIn("Biology", names)
        self.assertNotIn("History", names)

    def test_course_detail_without_workspace_context_fails(self):
        from apps.content.models import Subject, Course
        subj = Subject.objects.create(workspace=self.ws, name="English")
        course = Course.objects.create(workspace=self.ws, title="English 101", subject=subj)
        r = self._get(self.c, f"courses/{course.id}/", host=PLATFORM_HOST)
        self.assertIn(r.status_code, [400, 403, 404])


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class Scenario4_GroupAndStudent(E2EBase):
    """Scenario 4: Owner creates group and adds a student."""

    def setUp(self):
        super().setUp()
        self.owner = self._make_verified_user(email="owner_group@e2e.test")
        self.ws = self._make_workspace("e2e-groups", self.owner)
        self._activate_workspace(self.ws)
        self.host = _ws_host(self.ws.subdomain)
        self.c = self._login_client("owner_group@e2e.test", host=self.host)

    def test_create_group(self):
        r = self._post(self.c, "groups/", {"name": "Grade 10A", "status": "ACTIVE"}, host=self.host)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["name"], "Grade 10A")

    def test_add_student_to_group(self):
        from apps.groups.models import Group
        from apps.workspaces.models import WorkspaceMembership
        group = Group.objects.create(workspace=self.ws, name="Grade 11B", status="ACTIVE")
        student = self._make_verified_user(email="student_grp@e2e.test")
        WorkspaceMembership.objects.create(user=student, workspace=self.ws, role="STUDENT")
        r = self._post(self.c, f"groups/{group.id}/members/", {"student_id": student.id}, host=self.host)
        self.assertEqual(r.status_code, 201, r.content)

    def test_list_groups_workspace_scoped(self):
        from apps.groups.models import Group
        Group.objects.create(workspace=self.ws, name="Group Alpha", status="ACTIVE")
        other_owner = self._make_verified_user(email="other_grp_owner@e2e.test")
        other_ws = self._make_workspace("e2e-other-grp", other_owner)
        Group.objects.create(workspace=other_ws, name="Group Beta", status="ACTIVE")
        r = self._get(self.c, "groups/", host=self.host)
        self.assertEqual(r.status_code, 200)
        names = [g["name"] for g in r.json()]
        self.assertIn("Group Alpha", names)
        self.assertNotIn("Group Beta", names)


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class Scenario5_StudentEnrollment(E2EBase):
    """Scenario 5: Student enrollment in a course via API."""

    def setUp(self):
        super().setUp()
        self.owner = self._make_verified_user(email="owner_enroll@e2e.test")
        self.ws = self._make_workspace("e2e-enroll", self.owner)
        self._activate_workspace(self.ws)
        self.student = self._make_verified_user(email="student_enroll@e2e.test")
        from apps.workspaces.models import WorkspaceMembership
        WorkspaceMembership.objects.create(user=self.student, workspace=self.ws, role="STUDENT")
        self.host = _ws_host(self.ws.subdomain)
        self.c = self._login_client("owner_enroll@e2e.test", host=self.host)

    def test_enroll_student_in_course(self):
        from apps.content.models import Subject, Course
        subj = Subject.objects.create(workspace=self.ws, name="Science")
        course = Course.objects.create(workspace=self.ws, title="Science 101", subject=subj)
        r = self._post(self.c, "enrollments/", {
            "student_id": self.student.id,
            "enrollable_type": "COURSE",
            "enrollable_id": course.id,
        }, host=self.host)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["student_id"], self.student.id)

    def test_duplicate_enrollment_returns_conflict(self):
        from apps.content.models import Subject, Course
        subj = Subject.objects.create(workspace=self.ws, name="Art")
        course = Course.objects.create(workspace=self.ws, title="Art 101", subject=subj)
        self._post(self.c, "enrollments/", {
            "student_id": self.student.id, "enrollable_type": "COURSE", "enrollable_id": course.id,
        }, host=self.host)
        r = self._post(self.c, "enrollments/", {
            "student_id": self.student.id, "enrollable_type": "COURSE", "enrollable_id": course.id,
        }, host=self.host)
        self.assertIn(r.status_code, [409, 400], r.content)

    def test_list_enrollments_filterable_by_student(self):
        from apps.content.models import Subject, Course
        from apps.enrollment.models import Enrollment
        subj = Subject.objects.create(workspace=self.ws, name="Music")
        course = Course.objects.create(workspace=self.ws, title="Music 101", subject=subj)
        Enrollment.objects.create(
            workspace=self.ws, student_id=self.student.id, enrollable_type="COURSE", enrollable_id=course.id
        )
        r = self._get(self.c, "enrollments/", host=self.host, qs=f"?student_id={self.student.id}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.json()) >= 1)


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class Scenario6_StudentContentAccess(E2EBase):
    """Scenario 6: Student accesses only authorized content."""

    def setUp(self):
        super().setUp()
        self.owner = self._make_verified_user(email="owner_access@e2e.test")
        self.ws = self._make_workspace("e2e-access", self.owner)
        self._activate_workspace(self.ws)
        self.student = self._make_verified_user(email="student_access@e2e.test")
        from apps.workspaces.models import WorkspaceMembership
        WorkspaceMembership.objects.create(user=self.student, workspace=self.ws, role="STUDENT")
        self.host = _ws_host(self.ws.subdomain)
        self.sc = self._login_client("student_access@e2e.test", host=self.host)

    def test_student_can_list_courses(self):
        from apps.content.models import Subject, Course
        subj = Subject.objects.create(workspace=self.ws, name="Literature")
        Course.objects.create(workspace=self.ws, title="Published Course", subject=subj, visibility="PUBLISHED")
        r = self._get(self.sc, "courses/", host=self.host)
        self.assertEqual(r.status_code, 200)

    def test_student_cannot_create_subject(self):
        r = self._post(self.sc, "subjects/", {"name": "Unauthorized"}, host=self.host)
        self.assertEqual(r.status_code, 403, r.content)

    def test_student_is_not_member_of_other_workspace(self):
        other_owner = self._make_verified_user(email="other_owner_acc@e2e.test")
        other_ws = self._make_workspace("e2e-other-acc", other_owner)
        self._activate_workspace(other_ws)
        other_host = _ws_host(other_ws.subdomain)
        r = self._get(self.sc, "subjects/", host=other_host)
        self.assertIn(r.status_code, [403, 404])

    def test_unauthenticated_cannot_access_workspace(self):
        c = Client()
        r = self._get(c, "subjects/", host=self.host)
        self.assertIn(r.status_code, [401, 403])


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class Scenario7_8_ParentAccess(E2EBase):
    """Scenarios 7 & 8: Parent links/access; cannot see other students."""

    def setUp(self):
        super().setUp()
        self.owner = self._make_verified_user(email="owner_parent@e2e.test")
        self.ws = self._make_workspace("e2e-parent", self.owner)
        self._activate_workspace(self.ws)
        self.student1 = self._make_verified_user(email="student1_p@e2e.test")
        self.student2 = self._make_verified_user(email="student2_p@e2e.test")
        self.parent = self._make_verified_user(email="parent_p@e2e.test")
        from apps.workspaces.models import WorkspaceMembership
        WorkspaceMembership.objects.create(user=self.student1, workspace=self.ws, role="STUDENT")
        WorkspaceMembership.objects.create(user=self.student2, workspace=self.ws, role="STUDENT")
        WorkspaceMembership.objects.create(user=self.parent, workspace=self.ws, role="PARENT")
        self.host = _ws_host(self.ws.subdomain)

    def test_owner_can_create_parent_link(self):
        owner_c = self._login_client("owner_parent@e2e.test", host=self.host)
        r = self._post(owner_c, "parent-links/", {
            "parent_id": self.parent.id,
            "student_id": self.student1.id,
        }, host=self.host)
        self.assertEqual(r.status_code, 201, r.content)

    def test_parent_sees_only_own_children(self):
        from apps.parents.models import ParentStudentLink
        ParentStudentLink.objects.create(workspace=self.ws, parent_id=self.parent.id, student_id=self.student1.id)
        parent_c = self._login_client("parent_p@e2e.test", host=self.host)
        r = self._get(parent_c, "my-students/", host=self.host)
        self.assertEqual(r.status_code, 200)
        student_ids = [link["student_id"] for link in r.json()]
        self.assertIn(self.student1.id, student_ids)
        self.assertNotIn(self.student2.id, student_ids)

    def test_parent_without_link_sees_no_children(self):
        parent2 = self._make_verified_user(email="parent2_p@e2e.test")
        from apps.workspaces.models import WorkspaceMembership
        WorkspaceMembership.objects.create(user=parent2, workspace=self.ws, role="PARENT")
        p2_c = self._login_client("parent2_p@e2e.test", host=self.host)
        r = self._get(p2_c, "my-students/", host=self.host)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 0)

    def test_parent_cannot_create_link_without_permission(self):
        parent_c = self._login_client("parent_p@e2e.test", host=self.host)
        r = self._post(parent_c, "parent-links/", {
            "parent_id": self.parent.id,
            "student_id": self.student2.id,
        }, host=self.host)
        self.assertEqual(r.status_code, 403, r.content)


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class Scenario9_PaymentFlow(E2EBase):
    """Scenario 9: Owner records payment, approves and rejects via API."""

    def setUp(self):
        super().setUp()
        self.owner = self._make_verified_user(email="owner_pay@e2e.test")
        self.ws = self._make_workspace("e2e-payments", self.owner)
        self._activate_workspace(self.ws)
        self.student = self._make_verified_user(email="student_pay@e2e.test")
        from apps.workspaces.models import WorkspaceMembership
        WorkspaceMembership.objects.create(user=self.student, workspace=self.ws, role="STUDENT")
        self.host = _ws_host(self.ws.subdomain)
        self.oc = self._login_client("owner_pay@e2e.test", host=self.host)

    def test_create_student_payment(self):
        r = self._post(self.oc, "student-payments/", {
            "student": self.student.id,
            "payment_model": "WORKSPACE_MONTHLY",
            "amount_egp": "200.00",
        }, host=self.host)
        self.assertEqual(r.status_code, 201, r.content)

    def test_approve_payment_changes_status(self):
        from apps.payments.models import StudentPayment
        payment = StudentPayment.objects.create(
            workspace=self.ws, student=self.student,
            payment_model="WORKSPACE_MONTHLY", amount_egp="150.00", status="PENDING",
        )
        r = self._post(self.oc, f"student-payments/{payment.id}/approve/", {}, host=self.host)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["status"], "PAID")

    def test_reject_payment_requires_reason(self):
        from apps.payments.models import StudentPayment
        payment = StudentPayment.objects.create(
            workspace=self.ws, student=self.student,
            payment_model="WORKSPACE_MONTHLY", amount_egp="100.00", status="PENDING",
        )
        r = self._post(self.oc, f"student-payments/{payment.id}/reject/", {}, host=self.host)
        self.assertIn(r.status_code, [400, 422], r.content)

    def test_reject_payment_with_reason(self):
        from apps.payments.models import StudentPayment
        payment = StudentPayment.objects.create(
            workspace=self.ws, student=self.student,
            payment_model="WORKSPACE_MONTHLY", amount_egp="100.00", status="PENDING",
        )
        r = self._post(self.oc, f"student-payments/{payment.id}/reject/", {
            "reason": "Blurry image"
        }, host=self.host)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["status"], "REJECTED")


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class Scenario10_Reports(E2EBase):
    """Scenario 10: Reports reflect actual DB records."""

    def setUp(self):
        super().setUp()
        self.owner = self._make_verified_user(email="owner_rep@e2e.test")
        self.ws = self._make_workspace("e2e-reports", self.owner)
        self._activate_workspace(self.ws)
        self.student = self._make_verified_user(email="student_rep@e2e.test")
        from apps.workspaces.models import WorkspaceMembership
        WorkspaceMembership.objects.create(user=self.student, workspace=self.ws, role="STUDENT")
        self.host = _ws_host(self.ws.subdomain)
        self.c = self._login_client("owner_rep@e2e.test", host=self.host)

    def test_payment_report_reflects_paid_payment(self):
        from apps.payments.models import StudentPayment
        StudentPayment.objects.create(
            workspace=self.ws, student=self.student,
            payment_model="WORKSPACE_MONTHLY", amount_egp="300.00", status="PAID",
        )
        r = self._get(self.c, "reports/payments/", host=self.host)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertIn("by_status", data)
        paid_rows = [row for row in data["by_status"] if row["status"] == "PAID"]
        self.assertTrue(len(paid_rows) >= 1)
        self.assertGreater(float(data["paid_total_egp"]), 0)

    def test_enrollment_report_reflects_enrollments(self):
        from apps.content.models import Subject, Course
        from apps.enrollment.models import Enrollment
        subj = Subject.objects.create(workspace=self.ws, name="Report Subject")
        course = Course.objects.create(workspace=self.ws, title="Report Course", subject=subj)
        Enrollment.objects.create(
            workspace=self.ws, student_id=self.student.id, enrollable_type="COURSE", enrollable_id=course.id
        )
        r = self._get(self.c, "reports/enrollment/", host=self.host)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertGreater(data["total"], 0)

    def test_attendance_report_returns_structure(self):
        r = self._get(self.c, "reports/attendance/", host=self.host)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("by_student", r.json())
        self.assertIn("totals", r.json())

    def test_report_with_filter_params(self):
        r = self._get(self.c, "reports/enrollment/", host=self.host, qs="?enrollable_type=COURSE")
        self.assertEqual(r.status_code, 200)
        self.assertIn("total", r.json())


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class Scenario11_TeamPermissions(E2EBase):
    """Scenario 11: Team-member permissions enforced via real API requests."""

    def setUp(self):
        super().setUp()
        self.owner = self._make_verified_user(email="owner_team@e2e.test")
        self.ws = self._make_workspace("e2e-team", self.owner)
        self._activate_workspace(self.ws)
        self.teacher = self._make_verified_user(email="teacher_team@e2e.test")
        from apps.workspaces.models import WorkspaceMembership
        WorkspaceMembership.objects.create(user=self.teacher, workspace=self.ws, role="TEACHER")
        self.host = _ws_host(self.ws.subdomain)
        self.tc = self._login_client("teacher_team@e2e.test", host=self.host)

    def test_teacher_without_grant_cannot_create_subject(self):
        r = self._post(self.tc, "subjects/", {"name": "No Grant Subject"}, host=self.host)
        self.assertEqual(r.status_code, 403, r.content)

    def test_teacher_with_content_create_grant_can_create_subject(self):
        from apps.accounts.models import TeamMemberPermission
        from apps.accounts.enums import PermissionKey
        TeamMemberPermission.objects.create(
            user=self.teacher, workspace=self.ws, permission_key=PermissionKey.CONTENT_CREATE
        )
        r = self._post(self.tc, "subjects/", {"name": "Granted Subject"}, host=self.host)
        self.assertEqual(r.status_code, 201, r.content)

    def test_permission_grant_not_leaked_to_other_workspace(self):
        from apps.accounts.models import TeamMemberPermission
        from apps.accounts.enums import PermissionKey
        TeamMemberPermission.objects.create(
            user=self.teacher, workspace=self.ws, permission_key=PermissionKey.CONTENT_CREATE
        )
        other_owner = self._make_verified_user(email="other_owner_team@e2e.test")
        other_ws = self._make_workspace("e2e-team-other", other_owner)
        self._activate_workspace(other_ws)
        other_host = _ws_host(other_ws.subdomain)
        r = self._post(self.tc, "subjects/", {"name": "Cross WS Subject"}, host=other_host)
        self.assertIn(r.status_code, [403, 404])


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class Scenario12_CrossWorkspaceIsolation(E2EBase):
    """Scenario 12: Cross-workspace data isolation via real API requests."""

    def setUp(self):
        super().setUp()
        self.owner_a = self._make_verified_user(email="owner_a_iso@e2e.test")
        self.owner_b = self._make_verified_user(email="owner_b_iso@e2e.test")
        self.ws_a = self._make_workspace("e2e-iso-a", self.owner_a)
        self.ws_b = self._make_workspace("e2e-iso-b", self.owner_b)
        self._activate_workspace(self.ws_a)
        self._activate_workspace(self.ws_b)
        self.host_a = _ws_host(self.ws_a.subdomain)
        self.host_b = _ws_host(self.ws_b.subdomain)
        self.ca = self._login_client("owner_a_iso@e2e.test", host=self.host_a)
        self.cb = self._login_client("owner_b_iso@e2e.test", host=self.host_b)

    def test_payments_isolated(self):
        from apps.payments.models import StudentPayment
        student_a = self._make_verified_user(email="st_a_iso@e2e.test")
        from apps.workspaces.models import WorkspaceMembership
        WorkspaceMembership.objects.create(user=student_a, workspace=self.ws_a, role="STUDENT")
        StudentPayment.objects.create(
            workspace=self.ws_a, student=student_a,
            payment_model="WORKSPACE_MONTHLY", amount_egp="100.00",
        )
        r = self._get(self.cb, "student-payments/", host=self.host_b)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        items = data.get("results", data) if isinstance(data, dict) else data
        self.assertEqual(len(items), 0)

    def test_groups_isolated(self):
        from apps.groups.models import Group
        Group.objects.create(workspace=self.ws_a, name="WS-A Group", status="ACTIVE")
        r = self._get(self.cb, "groups/", host=self.host_b)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("WS-A Group", [g["name"] for g in r.json()])

    def test_subjects_isolated(self):
        from apps.content.models import Subject
        Subject.objects.create(workspace=self.ws_b, name="WS-B Secret Subject")
        r = self._get(self.ca, "subjects/", host=self.host_a)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("WS-B Secret Subject", [s["name"] for s in r.json()])

    def test_owner_a_not_member_of_ws_b(self):
        r = self._get(self.ca, "groups/", host=self.host_b)
        self.assertIn(r.status_code, [403, 404])


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class AdditionalChecks(E2EBase):
    """Additional: error codes, auth failures, scan callback, workspace context."""

    def setUp(self):
        super().setUp()
        self.owner = self._make_verified_user(email="owner_extra@e2e.test")
        self.ws = self._make_workspace("e2e-extra", self.owner)
        self._activate_workspace(self.ws)
        self.host = _ws_host(self.ws.subdomain)
        self.c = self._login_client("owner_extra@e2e.test", host=self.host)

    def test_404_on_nonexistent_course(self):
        r = self._get(self.c, "courses/999999/", host=self.host)
        self.assertEqual(r.status_code, 404, r.content)

    def test_workspace_context_missing_returns_error(self):
        r = self._get(self.c, "groups/", host=PLATFORM_HOST)
        self.assertIn(r.status_code, [400, 403])

    def test_unauthenticated_workspace_endpoint(self):
        c = Client()
        r = self._get(c, "groups/", host=self.host)
        self.assertIn(r.status_code, [401, 403])

    def test_scan_callback_without_secret_returns_403(self):
        from unittest.mock import patch
        with patch("django.conf.settings.SCANNER_CALLBACK_SECRET", "prod-secret"):
            r = Client().post(
                "/api/v1/files/1/scan-callback/",
                data=json.dumps({"clean": True}),
                content_type="application/json",
                HTTP_HOST=PLATFORM_HOST,
            )
            self.assertEqual(r.status_code, 403)

    def test_scan_callback_with_correct_secret(self):
        from apps.files.models import StoredFile
        from apps.core.enums import ScanStatus
        from unittest.mock import patch
        sf = StoredFile.objects.create(
            workspace=self.ws, key="e2e/test.pdf", original_name="test.pdf",
            content_type="application/pdf", size_bytes=1000,
            category="LESSON_DOCUMENT", scan_status=ScanStatus.PENDING,
            uploaded_by_id=self.owner.id,
        )
        with patch("django.conf.settings.SCANNER_CALLBACK_SECRET", "test-callback-secret"):
            r = Client().post(
                f"/api/v1/files/{sf.id}/scan-callback/",
                data=json.dumps({"clean": True}),
                content_type="application/json",
                HTTP_X_SCANNER_SECRET="test-callback-secret",
                HTTP_HOST=PLATFORM_HOST,
            )
            self.assertEqual(r.status_code, 200, r.content)
        sf.refresh_from_db()
        self.assertEqual(sf.scan_status, ScanStatus.CLEAN)

    def test_outsider_cannot_access_workspace(self):
        outsider = self._make_verified_user(email="outsider_extra@e2e.test")
        oc = self._login_client("outsider_extra@e2e.test", host=self.host)
        r = self._get(oc, "groups/", host=self.host)
        self.assertIn(r.status_code, [403, 404])

    def test_empty_payment_list_for_new_workspace(self):
        r = self._get(self.c, "student-payments/", host=self.host)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        items = data.get("results", data) if isinstance(data, dict) else data
        self.assertEqual(len(items), 0)

    def test_pagination_on_subjects(self):
        from apps.content.models import Subject
        for i in range(5):
            Subject.objects.create(workspace=self.ws, name=f"Paginated Subject {i}")
        r = self._get(self.c, "subjects/", host=self.host)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.json()) >= 5)
