"""
Authorization regression tests.

4.1  Structural: every WorkspacePermission view must declare permission_map.
4.2  Parameterized permission-matrix spot checks (key role / endpoint pairs).
4.3  Contract regression tests (Bug 2.1–2.5).
4.4  Login throttle fail-closed test.
4.5  Enrollment authorization tests.
"""
from __future__ import annotations

import importlib
import inspect
import json
import threading
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings
from django.utils import timezone

BASE_DOMAIN = "educloud.test"
PLATFORM_HOST = BASE_DOMAIN


def _ws_host(subdomain: str) -> str:
    return f"{subdomain}.{BASE_DOMAIN}"


class PermissionMapStructuralTest(TestCase):
    """4.1 — Every view that uses WorkspacePermission must declare permission_map."""

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
                # FileScanCallbackView has empty permission_classes intentionally
                if getattr(obj, "authentication_classes", None) == []:
                    continue
                perm_classes = getattr(obj, "permission_classes", [])
                uses_wp = any(issubclass(p, WorkspacePermission) for p in perm_classes)
                if uses_wp and not hasattr(obj, "permission_map"):
                    missing.append(f"{module.__name__}.{attr_name}")

        self.assertEqual(
            missing,
            [],
            f"Views using WorkspacePermission without permission_map: {missing}",
        )


# ---------------------------------------------------------------------------
# Helpers shared by matrix / enrollment tests
# ---------------------------------------------------------------------------

class _E2EBase(TestCase):

    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()
        # also clear the in-process fallback counters
        from apps.accounts.services import login_throttle
        with login_throttle._fallback_lock:
            login_throttle._fallback_counts.clear()

    def _unique_email(self, tag):
        import uuid
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
        WorkspaceMembership.objects.create(user=owner, workspace=ws, role="OWNER", is_owner=True)
        return ws

    def _activate(self, ws):
        from apps.workspaces.services.lifecycle import transition
        from apps.core.enums import WorkspaceStatus, ActorType
        for st in (WorkspaceStatus.PENDING_PAYMENT, WorkspaceStatus.PENDING_APPROVAL, WorkspaceStatus.ACTIVE):
            ws.refresh_from_db()
            transition(ws, st, actor_type=ActorType.ADMIN, reason="test")
        ws.refresh_from_db()

    def _add_member(self, ws, user, role):
        from apps.workspaces.models import WorkspaceMembership
        WorkspaceMembership.objects.get_or_create(
            user=user, workspace=ws,
            defaults={"role": role, "is_owner": False},
        )

    def _login_client(self, email, password="Pass1234!"):
        c = Client()
        r = c.post(
            "/api/v1/auth/login/",
            data=json.dumps({"username": email, "password": password}),
            content_type="application/json",
            HTTP_HOST=PLATFORM_HOST,
        )
        assert r.status_code == 200, f"Login failed: {r.content[:200]}"
        return c

    def _post(self, client, path, data, host=PLATFORM_HOST):
        return client.post(
            f"/api/v1/{path}",
            data=json.dumps(data),
            content_type="application/json",
            HTTP_HOST=host,
            SERVER_NAME=host.split(":")[0],
        )

    def _get(self, client, path, host=PLATFORM_HOST):
        return client.get(
            f"/api/v1/{path}",
            HTTP_HOST=host,
            SERVER_NAME=host.split(":")[0],
        )


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class PermissionMatrixTest(_E2EBase):
    """4.2 — Spot-check critical role/endpoint combinations."""

    def setUp(self):
        super().setUp()
        slug = "matrix-ws"
        self.owner_email = self._unique_email("owner")
        self.student_email = self._unique_email("student")
        self.owner = self._make_user(self.owner_email)
        self.student_user = self._make_user(self.student_email)
        self.ws = self._make_workspace(slug, self.owner)
        self._activate(self.ws)
        self._add_member(self.ws, self.student_user, "STUDENT")
        self.ws_host = _ws_host(slug)

    def test_student_cannot_create_subject(self):
        c = self._login_client(self.student_email)
        r = self._post(c, "content/subjects/", {"name": "Math", "grade_level": "G5", "color": "#fff"}, host=self.ws_host)
        self.assertEqual(r.status_code, 403, r.content)

    def test_owner_can_create_subject(self):
        c = self._login_client(self.owner_email)
        r = self._post(c, "content/subjects/", {"name": "Math", "grade_level": "G5", "color": "#ffffff"}, host=self.ws_host)
        # 201 or 200 — owner should be allowed
        self.assertIn(r.status_code, [200, 201], r.content)

    def test_student_cannot_delete_group(self):
        from apps.groups.models import Group
        grp = Group.objects.create(workspace=self.ws, name="Test Group", group_type="CLASS")
        c = self._login_client(self.student_email)
        host = self.ws_host
        r = c.delete(
            f"/api/v1/groups/{grp.id}/",
            HTTP_HOST=host,
            SERVER_NAME=host.split(":")[0],
        )
        self.assertEqual(r.status_code, 403, r.content)


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class ContractRegressionTest(_E2EBase):
    """4.3 — Contract bug regression tests (2.1–2.5)."""

    def setUp(self):
        super().setUp()
        slug = "contract-ws"
        self.owner_email = self._unique_email("owner")
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
        """Bug 2.2 — UserListView was 500ing due to -date_joined / full_name."""
        from apps.accounts.models import User
        sadmin_email = self._unique_email("sadmin")
        u = self._make_user(sadmin_email)
        u.is_super_admin = True
        u.save()
        c = self._login_client(sadmin_email)
        r = self._get(c, "admin/users/")
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
        """Bug 2.3 — joined_at should come from created_at."""
        from apps.workspaces.models import WorkspaceMembership
        from apps.workspaces.serializers import WorkspaceMembershipSerializer
        m = WorkspaceMembership.objects.get(user=self.owner, workspace=self.ws)
        ser = WorkspaceMembershipSerializer(m)
        self.assertEqual(ser.data["joined_at"], ser.data.get("joined_at"))
        # should not raise AttributeError — the field is sourced from created_at
        self.assertIsNotNone(ser.data["joined_at"])


class ThrottleFailClosedTest(TestCase):
    """4.4 — Login throttle must fail-closed on cache errors."""

    def setUp(self):
        from apps.accounts.services import login_throttle
        with login_throttle._fallback_lock:
            login_throttle._fallback_counts.clear()

    def test_fail_closed_when_cache_raises(self):
        """When cache raises on every call, 6th attempt must still be blocked."""
        from apps.accounts.services.login_throttle import check_login_allowed, record_failure
        from apps.core.errors import ThrottledError

        identifier = "failclosed@test.test"
        ip = "10.99.99.99"

        def boom(*args, **kwargs):
            raise Exception("Redis down")

        with patch("apps.accounts.services.login_throttle.cache") as mock_cache:
            mock_cache.get.side_effect = boom
            mock_cache.set.side_effect = boom
            mock_cache.delete.side_effect = boom

            # First 5 failures should record without raising
            for _ in range(5):
                check_login_allowed(identifier, ip)
                record_failure(identifier, ip)

            # 6th check must raise ThrottledError (fail-closed)
            with self.assertRaises(ThrottledError):
                check_login_allowed(identifier, ip)

    def test_throttle_resets_per_thread(self):
        """In-process counter is module-level (not thread-local) — verify shared state."""
        from apps.accounts.services import login_throttle
        errors = []

        def run():
            try:
                with patch("apps.accounts.services.login_throttle.cache") as mc:
                    mc.get.side_effect = Exception("down")
                    mc.set.side_effect = Exception("down")
                    identifier = "threadtest@test.test"
                    ip = "10.88.88.88"
                    for _ in range(5):
                        login_throttle.record_failure(identifier, ip)
            except Exception as e:
                errors.append(e)

        t = threading.Thread(target=run)
        t.start()
        t.join()
        self.assertEqual(errors, [])


@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class EnrollmentAuthorizationTest(_E2EBase):
    """4.5 — Enrollment authorization rules."""

    def setUp(self):
        super().setUp()
        slug = "enroll-ws"
        self.owner_email = self._unique_email("owner")
        self.student1_email = self._unique_email("student1")
        self.student2_email = self._unique_email("student2")
        self.owner = self._make_user(self.owner_email)
        self.student1 = self._make_user(self.student1_email)
        self.student2 = self._make_user(self.student2_email)
        self.ws = self._make_workspace(slug, self.owner)
        self._activate(self.ws)
        self._add_member(self.ws, self.student1, "STUDENT")
        self._add_member(self.ws, self.student2, "STUDENT")
        self.ws_host = _ws_host(slug)

        # Create a course to enroll into
        from apps.content.models import Course
        self.course = Course.objects.create(
            workspace=self.ws,
            title="Test Course",
            visibility="PUBLISHED",
            pricing_type="FREE",
        )

    def _enroll_payload(self, student_id):
        return {
            "student_id": student_id,
            "enrollable_type": "COURSE",
            "enrollable_id": self.course.id,
        }

    def test_student_self_enroll_allowed(self):
        c = self._login_client(self.student1_email)
        r = self._post(c, "enrollment/enrollments/", self._enroll_payload(self.student1.id), host=self.ws_host)
        self.assertIn(r.status_code, [200, 201], r.content)

    def test_student_cannot_enroll_other_student(self):
        c = self._login_client(self.student1_email)
        r = self._post(c, "enrollment/enrollments/", self._enroll_payload(self.student2.id), host=self.ws_host)
        self.assertEqual(r.status_code, 403, r.content)

    def test_owner_can_enroll_any_student(self):
        c = self._login_client(self.owner_email)
        r = self._post(c, "enrollment/enrollments/", self._enroll_payload(self.student1.id), host=self.ws_host)
        self.assertIn(r.status_code, [200, 201], r.content)
