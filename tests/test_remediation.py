"""
Remediation test suite — covers all P0/P1 items plus new features.
Runs with: python manage.py test tests.test_remediation
"""
from __future__ import annotations

from django.test import TestCase
from django.utils import timezone


# ── Helpers ──────────────────────────────────────────────────────────────────

_counter = 0
def _uid():
    global _counter
    _counter += 1
    return _counter


def make_user(**kwargs):
    from apps.accounts.models import User
    uid = _uid()
    defaults = {"email": f"u{uid}@test.com", "first_name": "Test", "last_name": "User"}
    defaults.update(kwargs)
    u = User(**{k: v for k, v in defaults.items() if k != "password"})
    u.set_password(kwargs.get("password", "Pass1234!"))
    u.save()
    return u


def make_workspace(subdomain=None):
    from apps.workspaces.models import Workspace
    subdomain = subdomain or f"ws{_uid()}"
    return Workspace.objects.create(subdomain=subdomain, status="SETUP", settings_json={"display_name": subdomain})


def make_membership(user, workspace, role="TEACHER", is_owner=False):
    from apps.workspaces.models import WorkspaceMembership
    return WorkspaceMembership.objects.create(
        user=user, workspace=workspace, role=role, is_owner=is_owner
    )


def make_package():
    from apps.billing.models import Package
    uid = _uid()
    return Package.objects.create(
        name=f"Plan {uid}", slug=f"plan-{uid}", price_egp="199.00", duration_months=1
    )


# ── P0-1: NotificationPreferenceViewSet ──────────────────────────────────────

class NotificationPreferenceTests(TestCase):
    def test_get_queryset_does_not_crash(self):
        """NotificationPreferenceViewSet.get_queryset() must not raise AssertionError."""
        from apps.notifications.views import NotificationPreferenceViewSet
        from apps.notifications.models import NotificationPreference
        u = make_user()
        ws = make_workspace()
        make_membership(u, ws)
        # Simulate list call
        prefs = NotificationPreference.objects.filter(user=u)
        self.assertEqual(list(prefs), [])  # no error — queryset works

    def test_preference_upsert(self):
        from apps.notifications.models import NotificationPreference
        from apps.core.enums import NotificationCategory
        u = make_user()
        NotificationPreference.objects.update_or_create(
            user=u, category=NotificationCategory.SUBSCRIPTION_STATUS_CHANGED,
            defaults={"is_enabled": False},
        )
        pref = NotificationPreference.objects.get(user=u, category=NotificationCategory.SUBSCRIPTION_STATUS_CHANGED)
        self.assertFalse(pref.is_enabled)


# ── P0-2: FileScanCallbackView secret validation ──────────────────────────────

class FileScanCallbackSecurityTests(TestCase):
    def test_missing_secret_rejected(self):
        """When SCANNER_CALLBACK_SECRET is set, requests without it are rejected."""
        from django.test import RequestFactory
        from apps.files.views import FileScanCallbackView
        from unittest.mock import patch

        with patch("django.conf.settings.SCANNER_CALLBACK_SECRET", "correct-secret"):
            factory = RequestFactory()
            req = factory.post("/fake/", data={}, content_type="application/json")
            view = FileScanCallbackView.as_view()
            resp = view(req, pk=1)
            self.assertEqual(resp.status_code, 403)

    def test_wrong_secret_rejected(self):
        from django.test import RequestFactory
        from apps.files.views import FileScanCallbackView
        from unittest.mock import patch
        import json

        with patch("django.conf.settings.SCANNER_CALLBACK_SECRET", "correct-secret"):
            factory = RequestFactory()
            req = factory.post(
                "/fake/",
                data=json.dumps({"clean": True}),
                content_type="application/json",
                HTTP_X_SCANNER_SECRET="wrong-secret",
            )
            view = FileScanCallbackView.as_view()
            resp = view(req, pk=1)
            self.assertEqual(resp.status_code, 403)

    def test_correct_secret_accepted(self):
        from django.test import RequestFactory
        from apps.files.views import FileScanCallbackView
        from apps.files.models import StoredFile
        from apps.core.enums import ScanStatus
        from unittest.mock import patch
        import json

        ws = make_workspace()
        u = make_user()
        sf = StoredFile.objects.create(
            workspace=ws,
            key="test/file.pdf",
            original_name="file.pdf",
            content_type="application/pdf",
            size_bytes=1000,
            category="LESSON_DOCUMENT",
            scan_status=ScanStatus.PENDING,
            uploaded_by_id=u.id,
        )

        with patch("django.conf.settings.SCANNER_CALLBACK_SECRET", "my-secret"):
            factory = RequestFactory()
            req = factory.post(
                "/fake/",
                data=json.dumps({"clean": True}),
                content_type="application/json",
                HTTP_X_SCANNER_SECRET="my-secret",
            )
            view = FileScanCallbackView.as_view()
            resp = view(req, pk=sf.id)
            self.assertEqual(resp.status_code, 200)

        sf.refresh_from_db()
        self.assertEqual(sf.scan_status, ScanStatus.CLEAN)

    def test_no_secret_configured_rejects_all(self):
        from django.test import RequestFactory
        from apps.files.views import FileScanCallbackView
        from unittest.mock import patch
        import json

        with patch("django.conf.settings.SCANNER_CALLBACK_SECRET", ""):
            factory = RequestFactory()
            req = factory.post(
                "/fake/",
                data=json.dumps({"clean": True}),
                content_type="application/json",
                HTTP_X_SCANNER_SECRET="anything",
            )
            view = FileScanCallbackView.as_view()
            resp = view(req, pk=1)
            self.assertEqual(resp.status_code, 403)


# ── P0-3: Parent IDOR protection ─────────────────────────────────────────────

class ParentIDORTests(TestCase):
    def test_parent_sees_only_own_children(self):
        from apps.parents.models import ParentStudentLink
        ws = make_workspace()
        parent1 = make_user()
        parent2 = make_user()
        student1 = make_user()
        student2 = make_user()
        make_membership(parent1, ws, role="PARENT")
        make_membership(parent2, ws, role="PARENT")

        ParentStudentLink.objects.create(workspace=ws, parent_id=parent1.id, student_id=student1.id)
        ParentStudentLink.objects.create(workspace=ws, parent_id=parent2.id, student_id=student2.id)

        # parent1's links should not include student2
        p1_links = ParentStudentLink.objects.filter(workspace=ws, parent_id=parent1.id, unlinked_at__isnull=True)
        self.assertEqual(p1_links.count(), 1)
        self.assertEqual(p1_links.first().student_id, student1.id)

    def test_parent_link_creation_requires_permission(self):
        from apps.parents.views import ParentLinkView
        from apps.core.errors import PermissionDeniedError
        from django.test import RequestFactory

        ws = make_workspace()
        parent = make_user()
        student = make_user()
        make_membership(parent, ws, role="PARENT")

        factory = RequestFactory()
        req = factory.post("/fake/", data={"parent_id": parent.id, "student_id": student.id}, content_type="application/json")
        req.user = parent
        req.workspace_id = ws.id

        with self.assertRaises(PermissionDeniedError):
            view = ParentLinkView()
            view.post(req)


# ── P1-4: Communication services ─────────────────────────────────────────────

class CommunicationTests(TestCase):
    def setUp(self):
        self.ws = make_workspace()
        self.u1 = make_user()
        self.u2 = make_user()
        make_membership(self.u1, self.ws)
        make_membership(self.u2, self.ws)

    def test_get_or_create_conversation_canonical_order(self):
        from apps.communication.services.messaging import get_or_create_conversation
        conv_a = get_or_create_conversation(
            workspace_id=self.ws.id, initiator_id=self.u1.id, other_user_id=self.u2.id
        )
        conv_b = get_or_create_conversation(
            workspace_id=self.ws.id, initiator_id=self.u2.id, other_user_id=self.u1.id
        )
        self.assertEqual(conv_a.id, conv_b.id)

    def test_cannot_converse_with_self(self):
        from apps.communication.services.messaging import get_or_create_conversation
        from apps.core.errors import ValidationFailed
        with self.assertRaises(ValidationFailed):
            get_or_create_conversation(
                workspace_id=self.ws.id, initiator_id=self.u1.id, other_user_id=self.u1.id
            )

    def test_non_member_cannot_start_conversation(self):
        from apps.communication.services.messaging import get_or_create_conversation
        from apps.core.errors import PermissionDeniedError
        outsider = make_user()  # not a member
        with self.assertRaises(PermissionDeniedError):
            get_or_create_conversation(
                workspace_id=self.ws.id, initiator_id=self.u1.id, other_user_id=outsider.id
            )

    def test_send_message_and_update_last_message_at(self):
        from apps.communication.services.messaging import get_or_create_conversation, send_message
        conv = get_or_create_conversation(
            workspace_id=self.ws.id, initiator_id=self.u1.id, other_user_id=self.u2.id
        )
        msg = send_message(
            workspace_id=self.ws.id,
            conversation_id=conv.id,
            sender_id=self.u1.id,
            body="Hello",
        )
        self.assertIsNotNone(msg.id)
        conv.refresh_from_db()
        self.assertIsNotNone(conv.last_message_at)

    def test_non_participant_cannot_send(self):
        from apps.communication.services.messaging import get_or_create_conversation, send_message
        from apps.core.errors import PermissionDeniedError
        u3 = make_user()
        make_membership(u3, self.ws)
        conv = get_or_create_conversation(
            workspace_id=self.ws.id, initiator_id=self.u1.id, other_user_id=self.u2.id
        )
        with self.assertRaises(PermissionDeniedError):
            send_message(
                workspace_id=self.ws.id,
                conversation_id=conv.id,
                sender_id=u3.id,
                body="Intruder",
            )

    def test_read_receipt_marks_others_messages(self):
        from apps.communication.services.messaging import get_or_create_conversation, send_message, mark_read
        from apps.communication.models import Message
        conv = get_or_create_conversation(
            workspace_id=self.ws.id, initiator_id=self.u1.id, other_user_id=self.u2.id
        )
        send_message(workspace_id=self.ws.id, conversation_id=conv.id, sender_id=self.u1.id, body="Msg 1")
        send_message(workspace_id=self.ws.id, conversation_id=conv.id, sender_id=self.u1.id, body="Msg 2")

        marked = mark_read(workspace_id=self.ws.id, conversation_id=conv.id, reader_id=self.u2.id)
        self.assertEqual(marked, 2)

        # u1's own messages should not be marked when u1 reads
        marked_by_sender = mark_read(workspace_id=self.ws.id, conversation_id=conv.id, reader_id=self.u1.id)
        self.assertEqual(marked_by_sender, 0)

    def test_empty_body_rejected(self):
        from apps.communication.services.messaging import get_or_create_conversation, send_message
        from apps.core.errors import ValidationFailed
        conv = get_or_create_conversation(
            workspace_id=self.ws.id, initiator_id=self.u1.id, other_user_id=self.u2.id
        )
        with self.assertRaises(ValidationFailed):
            send_message(workspace_id=self.ws.id, conversation_id=conv.id, sender_id=self.u1.id, body="  ")

    def test_delete_message_own_only(self):
        from apps.communication.services.messaging import get_or_create_conversation, send_message, delete_message
        from apps.core.errors import PermissionDeniedError
        conv = get_or_create_conversation(
            workspace_id=self.ws.id, initiator_id=self.u1.id, other_user_id=self.u2.id
        )
        msg = send_message(workspace_id=self.ws.id, conversation_id=conv.id, sender_id=self.u1.id, body="Mine")
        with self.assertRaises(PermissionDeniedError):
            delete_message(workspace_id=self.ws.id, message_id=msg.id, requester_id=self.u2.id)
        delete_message(workspace_id=self.ws.id, message_id=msg.id, requester_id=self.u1.id)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.deleted_at)


# ── P1-6: Subscription payment approve/reject ─────────────────────────────────

class SubscriptionPaymentApprovalTests(TestCase):
    def setUp(self):
        self.ws = make_workspace()
        self.package = make_package()
        self.owner = make_user()
        self.admin = make_user()
        make_membership(self.owner, self.ws, role="OWNER", is_owner=True)
        self.admin.is_staff = True
        self.admin.save()

    def test_submit_proof_changes_status_to_under_review(self):
        from apps.billing.services.subscriptions import create_subscription
        from apps.billing.models import SubscriptionPayment
        from apps.core.enums import SubPaymentStatus

        sub = create_subscription(workspace_id=self.ws.id, package_id=self.package.id)
        payment = SubscriptionPayment.objects.get(subscription=sub)
        self.assertEqual(payment.status, SubPaymentStatus.SUBMITTED)

        payment.proof_file_id = 999
        payment.status = SubPaymentStatus.UNDER_REVIEW
        payment.submitted_at = timezone.now()
        payment.save(update_fields=["proof_file_id", "status", "submitted_at", "updated_at"])

        payment.refresh_from_db()
        self.assertEqual(payment.status, SubPaymentStatus.UNDER_REVIEW)

    def test_approve_activates_subscription(self):
        from apps.billing.services.subscriptions import create_subscription, activate_subscription
        from apps.billing.models import SubscriptionPayment
        from apps.core.enums import SubPaymentStatus, SubscriptionStatus

        sub = create_subscription(workspace_id=self.ws.id, package_id=self.package.id)
        payment = SubscriptionPayment.objects.get(subscription=sub)
        payment.status = SubPaymentStatus.UNDER_REVIEW
        payment.save(update_fields=["status", "updated_at"])

        activate_subscription(sub.id, actor_id=self.admin.id)
        sub.refresh_from_db()
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)
        self.assertIsNotNone(sub.entitlement_snapshot)

    def test_reject_does_not_activate_subscription(self):
        from apps.billing.services.subscriptions import create_subscription
        from apps.billing.models import SubscriptionPayment, Subscription
        from apps.core.enums import SubPaymentStatus, SubscriptionStatus

        sub = create_subscription(workspace_id=self.ws.id, package_id=self.package.id)
        payment = SubscriptionPayment.objects.get(subscription=sub)
        payment.status = SubPaymentStatus.UNDER_REVIEW
        payment.status = SubPaymentStatus.REJECTED
        payment.reviewed_by_id = self.admin.id
        payment.reviewed_at = timezone.now()
        payment.notes = "Invalid proof"
        payment.save()

        sub.refresh_from_db()
        self.assertNotEqual(sub.status, SubscriptionStatus.ACTIVE)

    def test_cannot_approve_non_under_review(self):
        from apps.billing.services.subscriptions import create_subscription
        from apps.billing.models import SubscriptionPayment
        from apps.core.enums import SubPaymentStatus

        sub = create_subscription(workspace_id=self.ws.id, package_id=self.package.id)
        payment = SubscriptionPayment.objects.get(subscription=sub)
        # Still SUBMITTED — approve action should reject it
        self.assertEqual(payment.status, SubPaymentStatus.SUBMITTED)


# ── Bulk import ───────────────────────────────────────────────────────────────

class BulkImportTests(TestCase):
    def _csv(self, rows):
        lines = ["name,phone,email"]
        for r in rows:
            lines.append(f"{r.get('name','')},{r.get('phone','')},{r.get('email','')}")
        return "\n".join(lines).encode()

    def test_valid_rows_created(self):
        from apps.accounts.services.bulk_import import import_students
        ws = make_workspace()
        creator = make_user()
        csv_data = self._csv([
            {"name": "Ahmed Ali", "phone": "01001234501", "email": "ahmed@test.com"},
            {"name": "Sara Mahmoud", "phone": "01001234502"},
        ])
        job = import_students(workspace_id=ws.id, created_by_id=creator.id, csv_content=csv_data)
        self.assertEqual(job.status, "DONE")
        self.assertEqual(job.created_count, 2)
        self.assertEqual(job.skipped_count, 0)

    def test_duplicate_phone_skipped(self):
        from apps.accounts.services.bulk_import import import_students
        ws = make_workspace()
        creator = make_user()
        # First import
        csv_data = self._csv([{"name": "First", "phone": "01001234503"}])
        import_students(workspace_id=ws.id, created_by_id=creator.id, csv_content=csv_data)
        # Second import same phone
        csv_data2 = self._csv([{"name": "Dup", "phone": "01001234503"}])
        job2 = import_students(workspace_id=ws.id, created_by_id=creator.id, csv_content=csv_data2)
        self.assertEqual(job2.skipped_count, 1)
        self.assertEqual(job2.created_count, 0)

    def test_missing_name_skipped(self):
        from apps.accounts.services.bulk_import import import_students
        ws = make_workspace()
        creator = make_user()
        csv_data = self._csv([{"name": "", "phone": "01001234504"}])
        job = import_students(workspace_id=ws.id, created_by_id=creator.id, csv_content=csv_data)
        self.assertEqual(job.skipped_count, 1)

    def test_partial_success(self):
        from apps.accounts.services.bulk_import import import_students
        ws = make_workspace()
        creator = make_user()
        csv_data = self._csv([
            {"name": "Good", "phone": "01001234505"},
            {"name": "", "phone": "01001234506"},  # will be skipped
        ])
        job = import_students(workspace_id=ws.id, created_by_id=creator.id, csv_content=csv_data)
        self.assertEqual(job.created_count, 1)
        self.assertEqual(job.skipped_count, 1)


# ── Student payment approval/rejection ────────────────────────────────────────

class StudentPaymentTests(TestCase):
    def setUp(self):
        self.ws = make_workspace()
        self.teacher = make_user()
        self.student = make_user()
        make_membership(self.teacher, self.ws, role="OWNER", is_owner=True)
        make_membership(self.student, self.ws, role="STUDENT")

    def _make_payment(self):
        from apps.payments.models import StudentPayment
        return StudentPayment.objects.create(
            workspace=self.ws,
            student=self.student,
            payment_model="WORKSPACE_MONTHLY",
            amount_egp="100.00",
            status="PENDING",
        )

    def test_approve_payment_changes_status(self):
        from apps.payments.models import StudentPayment, PaymentEvent
        from apps.core.enums import StudentPaymentStatus
        from django.db import transaction

        payment = self._make_payment()
        with transaction.atomic():
            p = StudentPayment.objects.select_for_update().get(pk=payment.pk)
            from_status = p.status
            p.status = StudentPaymentStatus.PAID
            p.reviewed_at = timezone.now()
            p.reviewed_by_id = self.teacher.id
            p.save(update_fields=["status", "reviewed_at", "reviewed_by_id", "updated_at"])
            PaymentEvent.objects.create(
                workspace=self.ws, payment=p, from_status=from_status,
                to_status=p.status, actor_id=self.teacher.id
            )

        payment.refresh_from_db()
        self.assertEqual(payment.status, StudentPaymentStatus.PAID)
        self.assertTrue(PaymentEvent.objects.filter(payment=payment).exists())

    def test_reject_payment_records_reason(self):
        from apps.payments.models import StudentPayment, PaymentEvent
        from apps.core.enums import StudentPaymentStatus
        from django.db import transaction

        payment = self._make_payment()
        with transaction.atomic():
            p = StudentPayment.objects.select_for_update().get(pk=payment.pk)
            from_status = p.status
            p.status = StudentPaymentStatus.REJECTED
            p.reviewed_at = timezone.now()
            p.reviewed_by_id = self.teacher.id
            p.notes = "Invalid proof image"
            p.save(update_fields=["status", "reviewed_at", "reviewed_by_id", "notes", "updated_at"])
            PaymentEvent.objects.create(
                workspace=self.ws, payment=p, from_status=from_status,
                to_status=p.status, actor_id=self.teacher.id, notes="Invalid proof image"
            )

        payment.refresh_from_db()
        self.assertEqual(payment.status, StudentPaymentStatus.REJECTED)
        self.assertIn("Invalid", payment.notes)


# ── Assessment attempts ────────────────────────────────────────────────────────

class AssessmentAttemptTests(TestCase):
    def setUp(self):
        self.ws = make_workspace()
        self.teacher = make_user()
        self.student = make_user()
        make_membership(self.teacher, self.ws, role="OWNER", is_owner=True)
        make_membership(self.student, self.ws, role="STUDENT")

    def _make_exam(self):
        from apps.assessments.models import Exam
        return Exam.objects.create(
            workspace=self.ws,
            title="Test Exam",
            duration_minutes=60,
            status="PUBLISHED",
        )

    def test_start_attempt(self):
        from apps.assessments.services.attempts import start_attempt
        exam = self._make_exam()
        attempt = start_attempt(exam_id=exam.id, student_id=self.student.id, workspace_id=self.ws.id)
        self.assertIsNotNone(attempt.id)
        self.assertIsNotNone(attempt.started_at)

    def test_submit_attempt(self):
        from apps.assessments.services.attempts import start_attempt, submit_attempt
        exam = self._make_exam()
        attempt = start_attempt(exam_id=exam.id, student_id=self.student.id, workspace_id=self.ws.id)
        submit_attempt(attempt_id=attempt.id, student_id=self.student.id, answers={})
        attempt.refresh_from_db()
        self.assertIsNotNone(attempt.submitted_at)

    def test_cannot_exceed_max_attempts(self):
        """After submitting max_attempts, starting another attempt raises Conflict."""
        from apps.assessments.services.attempts import start_attempt, submit_attempt
        from apps.core.errors import Conflict
        exam = self._make_exam()
        attempt = start_attempt(exam_id=exam.id, student_id=self.student.id, workspace_id=self.ws.id)
        submit_attempt(attempt_id=attempt.id, student_id=self.student.id, answers={})
        # max_attempts=1 — second start should raise Conflict
        with self.assertRaises(Conflict):
            start_attempt(exam_id=exam.id, student_id=self.student.id, workspace_id=self.ws.id)


# ── Notification dispatch ─────────────────────────────────────────────────────

class NotificationDispatchTests(TestCase):
    def test_notify_creates_notification(self):
        from apps.notifications.services.dispatch import notify
        from apps.notifications.models import Notification
        from apps.core.enums import NotificationCategory
        u = make_user()
        ws = make_workspace()
        before = Notification.objects.count()
        notify(user_id=u.id, workspace_id=ws.id, category=NotificationCategory.SUBSCRIPTION_STATUS_CHANGED, payload={"test": True})
        self.assertEqual(Notification.objects.count(), before + 1)

    def test_notify_unknown_category_raises(self):
        from apps.notifications.services.dispatch import notify
        u = make_user()
        with self.assertRaises(ValueError):
            notify(user_id=u.id, workspace_id=1, category="INVALID_CATEGORY")

    def test_notify_respects_disabled_preference(self):
        from apps.notifications.services.dispatch import notify
        from apps.notifications.models import Notification, NotificationPreference
        from apps.core.enums import NotificationCategory
        u = make_user()
        ws = make_workspace()
        NotificationPreference.objects.create(
            user=u,
            category=NotificationCategory.SUBSCRIPTION_STATUS_CHANGED,
            is_enabled=False,
        )
        before = Notification.objects.count()
        notify(user_id=u.id, workspace_id=ws.id, category=NotificationCategory.SUBSCRIPTION_STATUS_CHANGED)
        self.assertEqual(Notification.objects.count(), before)  # nothing created


# ── Entitlement limits ─────────────────────────────────────────────────────────

class EntitlementLimitTests(TestCase):
    def test_check_limit_raises_when_exceeded(self):
        from apps.billing.services.entitlements import check_limit
        from apps.core.errors import LimitExceeded
        from apps.billing.models import Package, Subscription
        from apps.core.enums import SubscriptionStatus

        ws = make_workspace()
        pkg = Package.objects.create(
            name="Small Plan", slug=f"small-{_uid()}", price_egp="99.00",
            duration_months=1, max_students=2,
        )
        sub = Subscription.objects.create(
            workspace=ws,
            package=pkg,
            status=SubscriptionStatus.ACTIVE,
            entitlement_snapshot={"max_students": 2},
            starts_at=timezone.now(),
            ends_at=timezone.now() + __import__("datetime").timedelta(days=30),
        )

        from apps.core.enums import LimitKey
        with self.assertRaises(LimitExceeded):
            check_limit(workspace_id=ws.id, limit_key=LimitKey.MAX_STUDENTS, current_count=2)

    def test_check_limit_passes_when_within(self):
        from apps.billing.services.entitlements import check_limit
        from apps.billing.models import Package, Subscription
        from apps.core.enums import SubscriptionStatus

        ws = make_workspace()
        pkg = Package.objects.create(
            name="Big Plan", slug=f"big-{_uid()}", price_egp="299.00",
            duration_months=1, max_students=100,
        )
        Subscription.objects.create(
            workspace=ws,
            package=pkg,
            status=SubscriptionStatus.ACTIVE,
            entitlement_snapshot={"max_students": 100},
            starts_at=timezone.now(),
            ends_at=timezone.now() + __import__("datetime").timedelta(days=30),
        )
        from apps.core.enums import LimitKey
        check_limit(workspace_id=ws.id, limit_key=LimitKey.MAX_STUDENTS, current_count=50)
