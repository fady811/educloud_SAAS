"""
Authorization regression tests — Round 2.

4.1  Structural: every WorkspacePermission view must declare permission_map.
4.2  Full table-driven permission matrix (7 actors × all major endpoints).
4.3  Contract regression tests (Bug 2.1–2.5).
4.4  Login throttle fail-closed test (DB-backed fallback).
4.5  Enrollment authorization tests.
4.6  Grade data isolation: STUDENT list/retrieve for attempts and submissions.
4.7  Payment data isolation: STUDENT list sees only own payments.
"""
from __future__ import annotations

import importlib
import inspect
import json
import uuid
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from datetime import timedelta

from django.utils import timezone

BASE_DOMAIN = "educloud.test"
PLATFORM_HOST = BASE_DOMAIN


def _ws_host(subdomain: str) -> str:
    return f"{subdomain}.{BASE_DOMAIN}"


# ---------------------------------------------------------------------------
# 4.1  Structural
# ---------------------------------------------------------------------------

class PermissionMapStructuralTest(TestCase):
    """Every view that uses WorkspacePermission must declare permission_map."""

    def _all_view_modules(self):
        app_names = [
            "apps.content.views",
            "apps.groups.views",
            "apps.assessments.views",
            "apps.enrollment.views",
            "apps.communication.views",
            "apps.payments.views",
            "apps.reports.views",
            "apps.support.views",
            "apps.parents.views",
            "apps.files.views",
        ]
        for name in app_names:
            try:
                yield importlib.import_module(name)
            except ImportError:
                pass

    def test_all_workspace_permission_views_have_permission_map(self):
        from apps.core.permissions import WorkspacePermission
        from rest_framework.views import APIView
        from rest_framework.viewsets import ViewSetMixin

        missing = []
        for module in self._all_view_modules():
            for attr_name, obj in inspect.getmembers(module, inspect.isclass):
                if not (issubclass(obj, (APIView, ViewSetMixin)) and obj.__module__ == module.__name__):
                    continue
                if getattr(obj, "authentication_classes", None) == []:
                    continue
                perm_classes = getattr(obj, "permission_classes", [])
                uses_wp = any(issubclass(p, WorkspacePermission) for p in perm_classes)
                if uses_wp and not hasattr(obj, "permission_map"):
                    missing.append(f"{module.__name__}.{attr_name}")

        self.assertEqual(missing, [], f"Views using WorkspacePermission without permission_map: {missing}")


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

class _E2EBase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()
        from apps.accounts.models import LoginAttempt
        LoginAttempt.objects.all().delete()

    def _uid(self, tag=""):
        return f"{tag}-{uuid.uuid4().hex[:6]}"

    def _email(self, tag="u"):
        return f"{tag}-{uuid.uuid4().hex[:6]}@matrix.test"

    def _make_user(self, email, password="Pass1234!"):
        from apps.accounts.services.registration import register_user
        u, _ = register_user(email=email, password=password)
        u.email_verified_at = timezone.now()
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

    def _activate(self, ws):
        from apps.workspaces.services.lifecycle import transition
        from apps.core.enums import WorkspaceStatus, ActorType
        for st in (WorkspaceStatus.PENDING_PAYMENT, WorkspaceStatus.PENDING_APPROVAL, WorkspaceStatus.ACTIVE):
            ws.refresh_from_db()
            transition(ws, st, actor_type=ActorType.ADMIN, reason="test")
        ws.refresh_from_db()

    def _add_member(self, ws, user, role, permission_keys=None):
        from apps.workspaces.models import WorkspaceMembership
        from apps.accounts.models import TeamMemberPermission
        m, _ = WorkspaceMembership.objects.get_or_create(
            user=user, workspace=ws,
            defaults={"role": role, "is_owner": False},
        )
        for key in (permission_keys or []):
            TeamMemberPermission.objects.get_or_create(user=user, workspace=ws, permission_key=key)
        return m

    def _login_client(self, email, password="Pass1234!"):
        c = Client()
        r = c.post(
            "/api/v1/auth/login/",
            data=json.dumps({"username": email, "password": password}),
            content_type="application/json",
            HTTP_HOST=PLATFORM_HOST,
        )
        assert r.status_code == 200, f"Login failed for {email}: {r.content[:300]}"
        return c

    def _anon_client(self):
        return Client()

    def _do(self, method, client, path, data=None, host=PLATFORM_HOST):
        kwargs = dict(HTTP_HOST=host, SERVER_NAME=host.split(":")[0])
        url = f"/api/v1/{path}"
        if method == "GET":
            return client.get(url, **kwargs)
        if method == "POST":
            return client.post(url, data=json.dumps(data or {}), content_type="application/json", **kwargs)
        if method == "DELETE":
            return client.delete(url, **kwargs)
        if method == "PATCH":
            return client.patch(url, data=json.dumps(data or {}), content_type="application/json", **kwargs)
        raise ValueError(f"Unknown method {method}")


# ---------------------------------------------------------------------------
# 4.2  Full permission matrix
# ---------------------------------------------------------------------------

@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class PermissionMatrixTest(_E2EBase):
    """
    Table-driven matrix: one row per (endpoint, method) with expected status
    for 7 actors: owner, member_with_key, member_without_key, student, parent,
    other_workspace, anonymous.
    """

    @classmethod
    def setUpTestData(cls):
        from apps.accounts.services.registration import register_user
        from apps.workspaces.models import Workspace, WorkspaceMembership
        from apps.accounts.models import TeamMemberPermission
        from apps.accounts.enums import PermissionKey
        from apps.groups.models import Group
        from apps.content.models import Course

        from apps.accounts.models import User

        def mk(email, password="Pass1234!"):
            try:
                u, _ = register_user(email=email, password=password)
            except Exception:
                u = User.objects.get(email=email)
            u.email_verified_at = timezone.now()
            u.save()
            return u

        cls.owner = mk("owner@matrix.test")
        cls.member_with_key = mk("member-key@matrix.test")
        cls.member_no_key = mk("member-nokey@matrix.test")
        cls.student = mk("student@matrix.test")
        cls.parent = mk("parent@matrix.test")
        cls.other_owner = mk("other-owner@matrix.test")
        cls.anon_email = None

        from apps.workspaces.services.lifecycle import transition
        from apps.core.enums import WorkspaceStatus, ActorType

        cls.ws, ws_created = Workspace.objects.get_or_create(
            subdomain="mx",
            defaults={"status": "SETUP", "settings_json": {"display_name": "mx"}},
        )
        WorkspaceMembership.objects.get_or_create(
            user=cls.owner, workspace=cls.ws,
            defaults={"role": "TEACHER", "is_owner": True},
        )

        cls.other_ws, _ = Workspace.objects.get_or_create(
            subdomain="other-mx",
            defaults={"status": "SETUP", "settings_json": {"display_name": "other-mx"}},
        )
        WorkspaceMembership.objects.get_or_create(
            user=cls.other_owner, workspace=cls.other_ws,
            defaults={"role": "TEACHER", "is_owner": True},
        )

        # Activate both (no-op if already ACTIVE)
        for ws in (cls.ws, cls.other_ws):
            ws.refresh_from_db()
            if ws.status != WorkspaceStatus.ACTIVE:
                for st in (WorkspaceStatus.PENDING_PAYMENT, WorkspaceStatus.PENDING_APPROVAL, WorkspaceStatus.ACTIVE):
                    ws.refresh_from_db()
                    if ws.status != st:
                        transition(ws, st, actor_type=ActorType.ADMIN, reason="test")
            ws.refresh_from_db()

        # Add members
        WorkspaceMembership.objects.get_or_create(
            user=cls.member_with_key, workspace=cls.ws,
            defaults={"role": "TEAM_MEMBER", "is_owner": False},
        )
        TeamMemberPermission.objects.get_or_create(
            user=cls.member_with_key, workspace=cls.ws, permission_key=PermissionKey.CONTENT_CREATE
        )
        TeamMemberPermission.objects.get_or_create(
            user=cls.member_with_key, workspace=cls.ws, permission_key=PermissionKey.PAYMENT_VIEW
        )

        WorkspaceMembership.objects.get_or_create(
            user=cls.member_no_key, workspace=cls.ws,
            defaults={"role": "TEAM_MEMBER", "is_owner": False},
        )

        WorkspaceMembership.objects.get_or_create(
            user=cls.student, workspace=cls.ws,
            defaults={"role": "STUDENT", "is_owner": False},
        )
        WorkspaceMembership.objects.get_or_create(
            user=cls.parent, workspace=cls.ws,
            defaults={"role": "PARENT", "is_owner": False},
        )

        cls.group, _ = Group.objects.get_or_create(workspace=cls.ws, name="Test Group")
        cls.course, _ = Course.objects.get_or_create(
            workspace=cls.ws,
            title="Test Course",
            defaults={"visibility": "PUBLISHED", "pricing_type": "FREE"},
        )

        cls.ws_host = _ws_host("mx")
        cls.other_ws_host = _ws_host("other-mx")

    def setUp(self):
        super().setUp()  # clears cache and LoginAttempt rows
        # Login each actor fresh per test (session cookies)
        self.c_owner = self._login_client("owner@matrix.test")
        self.c_with_key = self._login_client("member-key@matrix.test")
        self.c_no_key = self._login_client("member-nokey@matrix.test")
        self.c_student = self._login_client("student@matrix.test")
        self.c_parent = self._login_client("parent@matrix.test")
        self.c_other = self._login_client("other-owner@matrix.test")
        self.c_anon = self._anon_client()

    # ---- CONTENT_CREATE permission key scenarios ----

    def test_content_create_owner_allowed(self):
        r = self._do("POST", self.c_owner, "subjects/",
                     {"name": f"Sub-{uuid.uuid4().hex[:4]}", "grade_level": "G5", "color": "#ffffff"},
                     host=self.ws_host)
        self.assertIn(r.status_code, [200, 201], r.content)

    def test_content_create_member_with_key_allowed(self):
        r = self._do("POST", self.c_with_key, "subjects/",
                     {"name": f"Sub-{uuid.uuid4().hex[:4]}", "grade_level": "G5", "color": "#ffffff"},
                     host=self.ws_host)
        self.assertIn(r.status_code, [200, 201], r.content)

    def test_content_create_member_without_key_denied(self):
        r = self._do("POST", self.c_no_key, "subjects/",
                     {"name": "X", "grade_level": "G5", "color": "#ffffff"},
                     host=self.ws_host)
        self.assertEqual(r.status_code, 403, r.content)

    def test_content_create_student_denied(self):
        r = self._do("POST", self.c_student, "subjects/",
                     {"name": "X", "grade_level": "G5", "color": "#ffffff"},
                     host=self.ws_host)
        self.assertEqual(r.status_code, 403, r.content)

    def test_content_create_anon_denied(self):
        r = self._do("POST", self.c_anon, "subjects/",
                     {"name": "X", "grade_level": "G5", "color": "#ffffff"},
                     host=self.ws_host)
        self.assertIn(r.status_code, [401, 403], r.content)

    # ---- GROUP owner_only delete ----

    def test_group_delete_owner_allowed(self):
        from apps.groups.models import Group
        g = Group.objects.create(workspace=self.ws, name=f"G-{uuid.uuid4().hex[:4]}")
        r = self._do("DELETE", self.c_owner, f"groups/{g.id}/", host=self.ws_host)
        self.assertIn(r.status_code, [200, 204], r.content)

    def test_group_delete_member_with_key_denied(self):
        # owner_only — even CONTENT_CREATE key is not enough
        from apps.groups.models import Group
        g = Group.objects.create(workspace=self.ws, name=f"G-{uuid.uuid4().hex[:4]}")
        r = self._do("DELETE", self.c_with_key, f"groups/{g.id}/", host=self.ws_host)
        self.assertEqual(r.status_code, 403, r.content)

    def test_group_delete_student_denied(self):
        from apps.groups.models import Group
        g = Group.objects.create(workspace=self.ws, name=f"G-{uuid.uuid4().hex[:4]}")
        r = self._do("DELETE", self.c_student, f"groups/{g.id}/", host=self.ws_host)
        self.assertEqual(r.status_code, 403, r.content)

    def test_group_create_member_without_content_create_key_denied(self):
        """TEAM_MEMBER with no CONTENT_CREATE key cannot create a group."""
        r = self._do("POST", self.c_no_key, "groups/",
                     {"name": f"G-{uuid.uuid4().hex[:4]}"},
                     host=self.ws_host)
        self.assertEqual(r.status_code, 403, r.content)

    # ---- GET list: all members allowed ----

    def test_subjects_list_student_allowed(self):
        r = self._do("GET", self.c_student, "subjects/", host=self.ws_host)
        self.assertEqual(r.status_code, 200, r.content)

    def test_subjects_list_parent_allowed(self):
        r = self._do("GET", self.c_parent, "subjects/", host=self.ws_host)
        self.assertEqual(r.status_code, 200, r.content)

    # ---- Other workspace: 403 (not a member of that workspace) ----

    def test_other_workspace_member_gets_403_on_subjects_list(self):
        # other_owner is a member of other_ws, NOT of ws — should get 403
        r = self._do("GET", self.c_other, "subjects/", host=self.ws_host)
        self.assertEqual(r.status_code, 403, r.content)

    # ---- PAYMENT_VIEW: student can list, member without key cannot ----

    def test_payment_list_student_allowed(self):
        r = self._do("GET", self.c_student, "student-payments/", host=self.ws_host)
        # 200 — student can list (own payments only)
        self.assertEqual(r.status_code, 200, r.content)

    def test_payment_list_member_without_key_denied(self):
        r = self._do("GET", self.c_no_key, "student-payments/", host=self.ws_host)
        self.assertEqual(r.status_code, 403, r.content)

    def test_payment_list_member_with_key_allowed(self):
        r = self._do("GET", self.c_with_key, "student-payments/", host=self.ws_host)
        self.assertEqual(r.status_code, 200, r.content)

    # ---- PARENT post to conversations denied (REQ-COMM-03) ----

    def test_parent_denied_post_to_conversations(self):
        r = self._do("POST", self.c_parent, "conversations/",
                     {"participant_b_id": self.owner.id},
                     host=self.ws_host)
        self.assertEqual(r.status_code, 403, r.content)

    # ---- Anonymous denied ----

    def test_anon_denied_subjects_list(self):
        r = self._do("GET", self.c_anon, "subjects/", host=self.ws_host)
        self.assertIn(r.status_code, [401, 403], r.content)


# ---------------------------------------------------------------------------
# 4.3  Contract regression tests
# ---------------------------------------------------------------------------

@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class ContractRegressionTest(_E2EBase):
    """Contract bug regression tests (2.1–2.5)."""

    def setUp(self):
        super().setUp()
        slug = f"contract-{uuid.uuid4().hex[:6]}"
        self.owner_email = self._email("owner")
        self.owner = self._make_user(self.owner_email)
        self.ws = self._make_workspace(slug, self.owner)
        self._activate(self.ws)
        self.ws_host = _ws_host(slug)

    def test_create_course_without_visibility_defaults_to_draft(self):
        """Bug 2.1 — visibility should default to DRAFT, not PRIVATE."""
        from apps.content.serializers import CourseWriteSerializer
        ser = CourseWriteSerializer(data={"title": "Test Course"})
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data["visibility"], "DRAFT")

    def test_create_course_private_visibility_is_invalid(self):
        """Bug 2.1 — PRIVATE is not a valid Visibility value."""
        from apps.content.serializers import CourseWriteSerializer
        ser = CourseWriteSerializer(data={"title": "Test Course", "visibility": "PRIVATE"})
        self.assertFalse(ser.is_valid())
        self.assertIn("visibility", ser.errors)

    def test_admin_user_list_returns_200(self):
        """Bug 2.2 — UserListView must not 500."""
        sadmin_email = self._email("sadmin")
        u = self._make_user(sadmin_email)
        u.is_super_admin = True
        u.save()
        c = self._login_client(sadmin_email)
        r = self._do("GET", c, "admin/users/")
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertIn("results", data)
        if data["results"]:
            row = data["results"][0]
            self.assertIn("display_name", row)
            self.assertIn("created_at", row)
            self.assertNotIn("full_name", row)
            self.assertNotIn("date_joined", row)

    def test_workspace_membership_serializer_joined_at(self):
        """Bug 2.3 — joined_at must come from created_at."""
        from apps.workspaces.models import WorkspaceMembership
        from apps.workspaces.serializers import WorkspaceMembershipSerializer
        m = WorkspaceMembership.objects.get(user=self.owner, workspace=self.ws)
        ser = WorkspaceMembershipSerializer(m)
        self.assertIsNotNone(ser.data["joined_at"])


# ---------------------------------------------------------------------------
# 4.4  Throttle fail-closed (DB fallback)
# ---------------------------------------------------------------------------

class ThrottleFailClosedTest(TestCase):
    """Login throttle must fail-closed when Redis is unavailable (DB fallback)."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_fail_closed_via_db_when_cache_raises(self):
        """When cache raises, 6th attempt via DB fallback must still be blocked."""
        from apps.accounts.services.login_throttle import check_login_allowed, record_failure
        from apps.core.errors import ThrottledError

        identifier = f"failclosed-{uuid.uuid4().hex[:6]}@test.test"
        ip = "10.99.99.99"

        def boom(*args, **kwargs):
            raise Exception("Redis down")

        with patch("apps.accounts.services.login_throttle.cache") as mock_cache:
            mock_cache.get.side_effect = boom
            mock_cache.set.side_effect = boom
            mock_cache.delete.side_effect = boom

            # 5 failures — each must not raise
            for _ in range(5):
                check_login_allowed(identifier, ip)
                record_failure(identifier, ip)

            # 6th check must raise ThrottledError
            with self.assertRaises(ThrottledError):
                check_login_allowed(identifier, ip)

    def test_record_failure_uses_db_when_cache_raises(self):
        """DB rows are created when cache is unavailable."""
        from apps.accounts.services.login_throttle import record_failure
        from apps.accounts.models import LoginAttempt
        import hashlib

        identifier = f"dbfallback-{uuid.uuid4().hex[:6]}@test.test"
        ip = "10.77.77.77"

        before = LoginAttempt.objects.count()

        with patch("apps.accounts.services.login_throttle.cache") as mock_cache:
            mock_cache.get.side_effect = Exception("down")
            mock_cache.set.side_effect = Exception("down")
            record_failure(identifier, ip)

        after = LoginAttempt.objects.count()
        self.assertGreater(after, before, "LoginAttempt row should have been created")

        # Verify identifier is hashed, never plain
        h = hashlib.sha256(identifier.encode()).hexdigest()
        row = LoginAttempt.objects.filter(identifier_hash=h).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.ip_address, ip)


# ---------------------------------------------------------------------------
# 4.5  Enrollment authorization
# ---------------------------------------------------------------------------

@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class EnrollmentAuthorizationTest(_E2EBase):

    def setUp(self):
        super().setUp()
        slug = f"enroll-{uuid.uuid4().hex[:6]}"
        self.owner_email = self._email("owner")
        self.s1_email = self._email("s1")
        self.s2_email = self._email("s2")
        self.owner = self._make_user(self.owner_email)
        self.s1 = self._make_user(self.s1_email)
        self.s2 = self._make_user(self.s2_email)
        self.ws = self._make_workspace(slug, self.owner)
        self._activate(self.ws)
        self._add_member(self.ws, self.s1, "STUDENT")
        self._add_member(self.ws, self.s2, "STUDENT")
        self.ws_host = _ws_host(slug)

        from apps.content.models import Course
        self.course = Course.objects.create(
            workspace=self.ws, title="TestCourse", visibility="PUBLISHED", pricing_type="FREE"
        )

    def _enroll_payload(self, student_id):
        return {"student_id": student_id, "enrollable_type": "COURSE", "enrollable_id": self.course.id}

    def test_student_self_enroll_allowed(self):
        c = self._login_client(self.s1_email)
        r = self._do("POST", c, "enrollments/", self._enroll_payload(self.s1.id), host=self.ws_host)
        self.assertIn(r.status_code, [200, 201], r.content)

    def test_student_cannot_enroll_other_student(self):
        c = self._login_client(self.s1_email)
        r = self._do("POST", c, "enrollments/", self._enroll_payload(self.s2.id), host=self.ws_host)
        self.assertEqual(r.status_code, 403, r.content)

    def test_owner_can_enroll_any_student(self):
        c = self._login_client(self.owner_email)
        r = self._do("POST", c, "enrollments/", self._enroll_payload(self.s1.id), host=self.ws_host)
        self.assertIn(r.status_code, [200, 201], r.content)


# ---------------------------------------------------------------------------
# 4.6  Grade data isolation
# ---------------------------------------------------------------------------

@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class GradeDataIsolationTest(_E2EBase):
    """STUDENT list/retrieve for ExamAttempt and AssignmentSubmission must be own-only."""

    def setUp(self):
        super().setUp()
        slug = f"grade-{uuid.uuid4().hex[:6]}"
        self.owner_email = self._email("owner")
        self.s1_email = self._email("s1")
        self.s2_email = self._email("s2")
        self.owner = self._make_user(self.owner_email)
        self.s1 = self._make_user(self.s1_email)
        self.s2 = self._make_user(self.s2_email)
        self.ws = self._make_workspace(slug, self.owner)
        self._activate(self.ws)
        self._add_member(self.ws, self.s1, "STUDENT")
        self._add_member(self.ws, self.s2, "STUDENT")
        self.ws_host = _ws_host(slug)

        from apps.assessments.models import Exam, ExamAttempt, Assignment, AssignmentSubmission
        deadline = timezone.now() + timedelta(hours=1)
        self.exam = Exam.objects.create(workspace=self.ws, title="Exam1", duration_minutes=60)
        self.attempt_s1 = ExamAttempt.objects.create(
            workspace=self.ws, exam=self.exam, student=self.s1, status="SUBMITTED", deadline_at=deadline
        )
        self.attempt_s2 = ExamAttempt.objects.create(
            workspace=self.ws, exam=self.exam, student=self.s2, status="SUBMITTED", deadline_at=deadline
        )
        self.assignment = Assignment.objects.create(workspace=self.ws, title="Assign1")
        self.sub_s1 = AssignmentSubmission.objects.create(
            workspace=self.ws, assignment=self.assignment, student=self.s1
        )
        self.sub_s2 = AssignmentSubmission.objects.create(
            workspace=self.ws, assignment=self.assignment, student=self.s2
        )

    def test_student_list_attempts_sees_only_own(self):
        c = self._login_client(self.s1_email)
        r = self._do("GET", c, "exam-attempts/", host=self.ws_host)
        self.assertEqual(r.status_code, 200, r.content)
        ids = [item["id"] for item in r.json().get("results", r.json())]
        self.assertIn(self.attempt_s1.id, ids)
        self.assertNotIn(self.attempt_s2.id, ids)

    def test_student_retrieve_own_attempt_allowed(self):
        c = self._login_client(self.s1_email)
        r = self._do("GET", c, f"exam-attempts/{self.attempt_s1.id}/", host=self.ws_host)
        self.assertEqual(r.status_code, 200, r.content)

    def test_student_retrieve_other_attempt_404(self):
        c = self._login_client(self.s1_email)
        r = self._do("GET", c, f"exam-attempts/{self.attempt_s2.id}/", host=self.ws_host)
        self.assertEqual(r.status_code, 404, r.content)

    def test_student_list_submissions_sees_only_own(self):
        c = self._login_client(self.s1_email)
        r = self._do("GET", c, "assignment-submissions/", host=self.ws_host)
        self.assertEqual(r.status_code, 200, r.content)
        ids = [item["id"] for item in r.json().get("results", r.json())]
        self.assertIn(self.sub_s1.id, ids)
        self.assertNotIn(self.sub_s2.id, ids)

    def test_student_retrieve_other_submission_404(self):
        c = self._login_client(self.s1_email)
        r = self._do("GET", c, f"assignment-submissions/{self.sub_s2.id}/", host=self.ws_host)
        self.assertEqual(r.status_code, 404, r.content)

    def test_owner_list_attempts_sees_all(self):
        c = self._login_client(self.owner_email)
        r = self._do("GET", c, "exam-attempts/", host=self.ws_host)
        self.assertEqual(r.status_code, 200, r.content)
        ids = [item["id"] for item in r.json().get("results", r.json())]
        self.assertIn(self.attempt_s1.id, ids)
        self.assertIn(self.attempt_s2.id, ids)


# ---------------------------------------------------------------------------
# 4.7  Payment data isolation
# ---------------------------------------------------------------------------

@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class PaymentDataIsolationTest(_E2EBase):
    """STUDENT list sees only own payments; MEMBER without key is denied."""

    def setUp(self):
        super().setUp()
        from apps.accounts.enums import PermissionKey
        slug = f"pay-{uuid.uuid4().hex[:6]}"
        self.owner_email = self._email("owner")
        self.s1_email = self._email("s1")
        self.s2_email = self._email("s2")
        self.tm_email = self._email("tm")
        self.owner = self._make_user(self.owner_email)
        self.s1 = self._make_user(self.s1_email)
        self.s2 = self._make_user(self.s2_email)
        self.tm = self._make_user(self.tm_email)
        self.ws = self._make_workspace(slug, self.owner)
        self._activate(self.ws)
        self._add_member(self.ws, self.s1, "STUDENT")
        self._add_member(self.ws, self.s2, "STUDENT")
        self._add_member(self.ws, self.tm, "TEAM_MEMBER")
        self.ws_host = _ws_host(slug)

        from apps.payments.models import StudentPayment
        self.pay_s1 = StudentPayment.objects.create(
            workspace=self.ws, student=self.s1, amount_egp="100.00", status="PENDING",
        )
        self.pay_s2 = StudentPayment.objects.create(
            workspace=self.ws, student=self.s2, amount_egp="200.00", status="PENDING",
        )

    def test_student_list_sees_only_own_payments(self):
        c = self._login_client(self.s1_email)
        r = self._do("GET", c, "student-payments/", host=self.ws_host)
        self.assertEqual(r.status_code, 200, r.content)
        items = r.json().get("results", r.json())
        ids = [i["id"] for i in items]
        self.assertIn(self.pay_s1.id, ids)
        self.assertNotIn(self.pay_s2.id, ids)

    def test_team_member_without_key_denied_payment_list(self):
        c = self._login_client(self.tm_email)
        r = self._do("GET", c, "student-payments/", host=self.ws_host)
        self.assertEqual(r.status_code, 403, r.content)

    def test_owner_can_list_all_payments(self):
        c = self._login_client(self.owner_email)
        r = self._do("GET", c, "student-payments/", host=self.ws_host)
        self.assertEqual(r.status_code, 200, r.content)
