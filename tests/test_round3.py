"""
Round 3 tests — student management, verification, password reset, lesson content, and defect fixes.

5.1  Defect 3.1 — LessonParentType has COURSE; CHECK constraint migration applies cleanly.
5.2  Defect 3.2 — Enrollment GET is narrowed by role (STUDENT sees own, staff sees all).
5.3  Defect 3.3 — IsParentOfStudent uses correct field names + unlinked_at__isnull.
5.4  Defect 3.4 — EnrollmentListCreateView.post delegates to enroll() service.
5.5  Part 1.1 — create_student() and get_students() (full_name bug fixed).
5.6  Part 1.2 — CSV import with per-row limit check.
5.7  Part 1.3 — verify_token() sets email/phone_verified_at; resend_verification().
5.8  Part 1.4 — confirm_reset() revokes all sessions.
5.9  Part 2   — lesson_accessible() 7-step evaluation; LessonContentView access gate.
"""
from __future__ import annotations

import json
import uuid

from django.test import TestCase, Client, override_settings
from django.utils import timezone

BASE_DOMAIN = "educloud.test"
PLATFORM_HOST = BASE_DOMAIN


def _ws_host(subdomain: str) -> str:
    return f"{subdomain}.{BASE_DOMAIN}"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class _Base(TestCase):

    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()

    def _email(self, tag="u"):
        return f"{tag}-{uuid.uuid4().hex[:6]}@r3.test"

    def _make_user(self, email, password="Pass1234!", verified=True):
        from apps.accounts.services.registration import register_user
        u, _ = register_user(email=email, password=password)
        if verified:
            u.email_verified_at = timezone.now()
            u.is_active = True
            u.save()
        return u

    def _make_workspace(self, owner, subdomain=None):
        from apps.workspaces.models import Workspace, WorkspaceMembership
        from apps.workspaces.services.lifecycle import transition
        from apps.core.enums import WorkspaceStatus, ActorType
        slug = subdomain or f"ws-{uuid.uuid4().hex[:8]}"
        ws = Workspace.objects.create(
            subdomain=slug,
            status="SETUP",
            settings_json={"display_name": slug},
        )
        WorkspaceMembership.objects.create(user=owner, workspace=ws, role="TEACHER", is_owner=True)
        for st in (WorkspaceStatus.PENDING_PAYMENT, WorkspaceStatus.PENDING_APPROVAL, WorkspaceStatus.ACTIVE):
            ws.refresh_from_db()
            transition(ws, st, actor_type=ActorType.ADMIN, reason="test")
        ws.refresh_from_db()
        return ws

    def _add_member(self, ws, user, role):
        from apps.workspaces.models import WorkspaceMembership
        WorkspaceMembership.objects.get_or_create(
            user=user, workspace=ws, defaults={"role": role, "is_owner": False}
        )

    def _login(self, email, password="Pass1234!"):
        c = Client()
        r = c.post(
            "/api/v1/auth/login/",
            data=json.dumps({"username": email, "password": password}),
            content_type="application/json",
            HTTP_HOST=PLATFORM_HOST,
        )
        assert r.status_code == 200, f"Login failed: {r.content[:200]}"
        return c

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
        raise ValueError(method)


# ---------------------------------------------------------------------------
# 5.1  LessonParentType.COURSE exists
# ---------------------------------------------------------------------------

class LessonParentTypeTest(TestCase):

    def test_course_value_in_lesson_parent_type(self):
        from apps.core.enums import LessonParentType
        self.assertIn("COURSE", LessonParentType.values)

    def test_lesson_can_be_created_with_course_parent_type(self):
        from apps.content.models import Lesson
        from apps.workspaces.models import Workspace
        ws = Workspace.objects.create(subdomain="lpt-ws", status="ACTIVE", settings_json={})
        lesson = Lesson.objects.create(workspace=ws, parent_type="COURSE", parent_id=1, title="t", order=0)
        self.assertEqual(lesson.parent_type, "COURSE")

    def test_check_constraint_rejects_invalid_parent_type(self):
        from apps.content.models import Lesson
        from apps.workspaces.models import Workspace
        from django.db import IntegrityError
        ws = Workspace.objects.create(subdomain="lpt-ws2", status="ACTIVE", settings_json={})
        with self.assertRaises(IntegrityError):
            Lesson.objects.create(workspace=ws, parent_type="INVALID_TYPE", parent_id=1, title="t", order=0)


# ---------------------------------------------------------------------------
# 5.2  Enrollment GET narrowing by role
# ---------------------------------------------------------------------------

@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class EnrollmentQuerysetNarrowingTest(_Base):

    def setUp(self):
        super().setUp()
        self.owner_email = self._email("owner")
        self.s1_email = self._email("s1")
        self.s2_email = self._email("s2")
        self.owner = self._make_user(self.owner_email)
        self.s1 = self._make_user(self.s1_email)
        self.s2 = self._make_user(self.s2_email)
        self.ws = self._make_workspace(self.owner)
        self._add_member(self.ws, self.s1, "STUDENT")
        self._add_member(self.ws, self.s2, "STUDENT")
        self.ws_host = _ws_host(self.ws.subdomain)

        from apps.content.models import Course
        from apps.enrollment.models import Enrollment
        self.course = Course.objects.create(
            workspace=self.ws, title="Course", visibility="PUBLISHED", pricing_type="FREE"
        )
        Enrollment.objects.create(
            workspace=self.ws, student_id=self.s1.id, enrollable_type="COURSE", enrollable_id=self.course.id
        )
        Enrollment.objects.create(
            workspace=self.ws, student_id=self.s2.id, enrollable_type="COURSE", enrollable_id=self.course.id
        )

    def test_student_sees_only_own_enrollments(self):
        c = self._login(self.s1_email)
        r = self._do("GET", c, "enrollments/", host=self.ws_host)
        self.assertEqual(r.status_code, 200)
        ids = [e["student_id"] for e in r.json()]
        self.assertTrue(all(i == self.s1.id for i in ids), ids)

    def test_owner_sees_all_enrollments(self):
        c = self._login(self.owner_email)
        r = self._do("GET", c, "enrollments/", host=self.ws_host)
        self.assertEqual(r.status_code, 200)
        student_ids = {e["student_id"] for e in r.json()}
        self.assertIn(self.s1.id, student_ids)
        self.assertIn(self.s2.id, student_ids)

    def test_student_retrieve_own_enrollment_200(self):
        from apps.enrollment.models import Enrollment
        e = Enrollment.objects.get(workspace=self.ws, student_id=self.s1.id)
        c = self._login(self.s1_email)
        r = self._do("GET", c, f"enrollments/{e.id}/", host=self.ws_host)
        self.assertEqual(r.status_code, 200)

    def test_student_retrieve_other_enrollment_404(self):
        from apps.enrollment.models import Enrollment
        e = Enrollment.objects.get(workspace=self.ws, student_id=self.s2.id)
        c = self._login(self.s1_email)
        r = self._do("GET", c, f"enrollments/{e.id}/", host=self.ws_host)
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# 5.3  IsParentOfStudent uses correct field names
# ---------------------------------------------------------------------------

class IsParentOfStudentFieldsTest(TestCase):

    def test_filter_uses_parent_id_and_student_id(self):
        from apps.core.permissions import IsParentOfStudent
        import inspect
        src = inspect.getsource(IsParentOfStudent.has_object_permission)
        self.assertIn("parent_id=", src)
        self.assertIn("student_id=", src)
        self.assertIn("unlinked_at__isnull=True", src)
        self.assertNotIn("parent_user", src)
        self.assertNotIn("student_user_id", src)


# ---------------------------------------------------------------------------
# 5.4  EnrollmentListCreateView.post delegates to enroll()
# ---------------------------------------------------------------------------

class EnrollmentDelegatesTest(TestCase):

    def test_post_uses_enroll_service(self):
        import inspect
        from apps.enrollment.views import EnrollmentListCreateView
        src = inspect.getsource(EnrollmentListCreateView.post)
        self.assertIn("from apps.enrollment.services.eligibility import enroll", src)
        self.assertNotIn("Enrollment.objects.create", src)


# ---------------------------------------------------------------------------
# 5.5  create_student() and get_students()
# ---------------------------------------------------------------------------

@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class StudentServiceTest(_Base):

    def setUp(self):
        super().setUp()
        self.owner_email = self._email("owner")
        self.owner = self._make_user(self.owner_email)
        self.ws = self._make_workspace(self.owner)

    def test_create_student_adds_membership(self):
        from apps.accounts.services.students import create_student
        from apps.workspaces.models import WorkspaceMembership
        m = create_student(
            workspace_id=self.ws.id,
            email=self._email("new"),
            first_name="Alice",
            last_name="Smith",
            actor_id=self.owner.id,
        )
        self.assertEqual(m.role, "STUDENT")
        self.assertEqual(m.workspace_id, self.ws.id)

    def test_get_students_orders_by_last_then_first(self):
        from apps.accounts.services.students import create_student, get_students
        create_student(workspace_id=self.ws.id, email=self._email("z"), first_name="Zara", last_name="Adams", actor_id=self.owner.id)
        create_student(workspace_id=self.ws.id, email=self._email("a"), first_name="Anna", last_name="Baker", actor_id=self.owner.id)
        qs = get_students(self.ws.id)
        names = [m.user.last_name for m in qs]
        self.assertEqual(names, sorted(names))


# ---------------------------------------------------------------------------
# 5.6  CSV import per-row limit check
# ---------------------------------------------------------------------------

class BulkImportLimitTest(TestCase):

    def test_import_row_skips_when_limit_exceeded(self):
        from apps.accounts.services.bulk_import import _import_row
        from apps.workspaces.models import Workspace
        from unittest.mock import patch

        ws = Workspace.objects.create(subdomain="import-ws-limit", status="ACTIVE", settings_json={})

        row = {"name": "Test User", "phone": "+201001234567", "email": ""}
        with patch("apps.billing.services.entitlements.check_limit") as mock_limit:
            from apps.core.errors import LimitExceeded
            mock_limit.side_effect = LimitExceeded(limit_key="MAX_STUDENTS", limit=1, current=1, remedy="upgrade")
            result = _import_row(None, 1, row, ws.id, None)
        self.assertEqual(result["status"], "SKIPPED")
        self.assertEqual(result["error_code"], "LIMIT_EXCEEDED")


# ---------------------------------------------------------------------------
# 5.7  verify_token() sets email/phone_verified_at; resend_verification()
# ---------------------------------------------------------------------------

class VerificationTest(TestCase):

    def test_verify_token_sets_email_verified_at(self):
        from apps.accounts.services.registration import register_user
        from apps.accounts.services.verification import verify_token

        u, vt = register_user(email="verify_test@t.com", password="Pass1234!")
        self.assertIsNone(u.email_verified_at)
        verify_token(vt._raw_token)
        u.refresh_from_db()
        self.assertIsNotNone(u.email_verified_at)
        self.assertTrue(u.is_active)

    def test_resend_verification_creates_new_token(self):
        from apps.accounts.services.registration import register_user
        from apps.accounts.services.verification import resend_verification
        from apps.accounts.models import VerificationToken

        u, _ = register_user(email="resend_test@t.com", password="Pass1234!")
        initial_count = VerificationToken.objects.filter(user=u).count()
        vt = resend_verification(u)
        self.assertIsNotNone(vt._raw_token)
        new_count = VerificationToken.objects.filter(user=u).count()
        self.assertEqual(new_count, initial_count + 1)

    def test_verify_endpoint_returns_200(self):
        from apps.accounts.services.registration import register_user
        u, vt = register_user(email="verify_ep@t.com", password="Pass1234!")
        c = Client()
        r = c.post(
            "/api/v1/auth/verify/",
            data=json.dumps({"token": vt._raw_token}),
            content_type="application/json",
            HTTP_HOST=PLATFORM_HOST,
        )
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# 5.8  confirm_reset() revokes all sessions
# ---------------------------------------------------------------------------

@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class PasswordResetTest(_Base):

    def test_confirm_reset_revokes_sessions(self):
        from apps.accounts.services.registration import register_user
        from apps.accounts.services.password_reset import request_reset, confirm_reset
        from apps.accounts.models import UserSession

        email = self._email("pwr")
        u, _ = register_user(email=email, password="Pass1234!")
        u.email_verified_at = timezone.now()
        u.is_active = True
        u.save()

        # Create a fake active session
        UserSession.objects.create(
            user=u,
            session_key_hash="fakehash1",
            workspace_id=None,
            device_info={},
            ip_address="127.0.0.1",
        )

        raw = request_reset(identifier=email)
        self.assertTrue(raw)
        confirm_reset(token=raw, new_password="NewPass999!")

        active_sessions = UserSession.objects.filter(user=u, revoked_at__isnull=True).count()
        self.assertEqual(active_sessions, 0)

    def test_password_reset_endpoint_flow(self):
        email = self._email("pwr2")
        u = self._make_user(email)
        c = Client()
        r = c.post(
            "/api/v1/auth/password-reset/",
            data=json.dumps({"email": email}),
            content_type="application/json",
            HTTP_HOST=PLATFORM_HOST,
        )
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# 5.9  lesson_accessible() and LessonContentView
# ---------------------------------------------------------------------------

@override_settings(BASE_DOMAIN=BASE_DOMAIN)
class LessonAccessTest(_Base):

    def setUp(self):
        super().setUp()
        self.owner_email = self._email("owner")
        self.student_email = self._email("student")
        self.owner = self._make_user(self.owner_email)
        self.student = self._make_user(self.student_email)
        self.ws = self._make_workspace(self.owner)
        self._add_member(self.ws, self.student, "STUDENT")
        self.ws_host = _ws_host(self.ws.subdomain)

        from apps.content.models import Course, Lesson
        self.course = Course.objects.create(
            workspace=self.ws, title="Course", visibility="PUBLISHED", pricing_type="FREE"
        )
        self.free_lesson = Lesson.objects.create(
            workspace=self.ws, parent_type="COURSE", parent_id=self.course.id,
            title="Free", order=0, is_free_preview=True,
        )
        self.paid_lesson = Lesson.objects.create(
            workspace=self.ws, parent_type="COURSE", parent_id=self.course.id,
            title="Paid", order=1, is_free_preview=False,
        )

    def _enroll_with_access(self, student):
        from apps.enrollment.models import Enrollment
        from apps.content.models import StudentCourseAccess
        Enrollment.objects.create(
            workspace=self.ws, student_id=student.id,
            enrollable_type="COURSE", enrollable_id=self.course.id,
        )
        StudentCourseAccess.objects.create(
            workspace=self.ws, student_id=student.id, course=self.course,
        )

    def test_free_preview_always_accessible(self):
        from apps.enrollment.services.access import lesson_accessible
        # No enrollment needed for free preview
        result = lesson_accessible(
            workspace_id=self.ws.id,
            student_id=self.student.id,
            lesson_id=self.free_lesson.id,
        )
        self.assertTrue(result)

    def test_free_course_inaccessible_without_enrollment(self):
        """
        Round 5 fix: FREE courses now allow enrolled students without an access row.
        But enrollment is still required — unenrolled students are denied.
        (Round 4 had this wrong: it trusted a test that was written before any access
        rows existed and asserted denial for everything. That locked in the bug.)
        """
        from apps.enrollment.services.access import lesson_accessible
        result = lesson_accessible(
            workspace_id=self.ws.id,
            student_id=self.student.id,
            lesson_id=self.paid_lesson.id,
        )
        self.assertFalse(result)  # not enrolled → ENROLLMENT_INACTIVE → False

    def test_free_course_accessible_with_enrollment_no_access_row(self):
        """
        An enrolled student on a FREE course must be able to view any non-preview lesson
        without a StudentCourseAccess row (no payment step).
        """
        from apps.enrollment.services.access import lesson_accessible
        from apps.enrollment.models import Enrollment
        Enrollment.objects.create(
            workspace=self.ws, student_id=self.student.id,
            enrollable_type="COURSE", enrollable_id=self.course.id,
        )
        # No StudentCourseAccess row — should still be True for FREE course
        result = lesson_accessible(
            workspace_id=self.ws.id,
            student_id=self.student.id,
            lesson_id=self.paid_lesson.id,
        )
        self.assertTrue(result)

    def test_paid_lesson_accessible_with_enrollment_and_access(self):
        from apps.enrollment.services.access import lesson_accessible
        self._enroll_with_access(self.student)
        result = lesson_accessible(
            workspace_id=self.ws.id,
            student_id=self.student.id,
            lesson_id=self.paid_lesson.id,
        )
        self.assertTrue(result)

    def test_lesson_content_endpoint_student_no_access_denied(self):
        """Unenrolled student gets 403."""
        c = self._login(self.student_email)
        r = self._do("GET", c, f"lessons/{self.paid_lesson.id}/content/", host=self.ws_host)
        self.assertEqual(r.status_code, 403)

    def test_lesson_content_endpoint_free_preview_allowed(self):
        c = self._login(self.student_email)
        r = self._do("GET", c, f"lessons/{self.free_lesson.id}/content/", host=self.ws_host)
        self.assertEqual(r.status_code, 200)

    def test_lesson_content_endpoint_owner_always_allowed(self):
        c = self._login(self.owner_email)
        r = self._do("GET", c, f"lessons/{self.paid_lesson.id}/content/", host=self.ws_host)
        self.assertEqual(r.status_code, 200)

    def test_expired_access_denies_student(self):
        """
        An expired StudentCourseAccess row on a MONTHLY course must deny the student.
        Uses a separate MONTHLY course to avoid the FREE-course bypass (step 4b).
        """
        from apps.enrollment.services.access import lesson_accessible
        from apps.content.models import Course, Lesson, StudentCourseAccess
        from apps.enrollment.models import Enrollment
        from datetime import timedelta

        # Create a MONTHLY (paid) course with one non-preview lesson
        paid_course = Course.objects.create(
            workspace=self.ws, title="Monthly Course",
            visibility="PUBLISHED", pricing_type="MONTHLY",
        )
        paid_lesson2 = Lesson.objects.create(
            workspace=self.ws, parent_type="COURSE", parent_id=paid_course.id,
            title="Paid2", order=0, is_free_preview=False,
        )
        Enrollment.objects.create(
            workspace=self.ws, student_id=self.student.id,
            enrollable_type="COURSE", enrollable_id=paid_course.id,
        )
        StudentCourseAccess.objects.create(
            workspace=self.ws, student_id=self.student.id, course=paid_course,
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(lesson_accessible(
            workspace_id=self.ws.id, student_id=self.student.id, lesson_id=paid_lesson2.id
        ))
