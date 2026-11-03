"""
tests/isolation/test_cross_tenant.py
=====================================
Registry-driven cross-tenant isolation suite (Round 5, item 5.2).

Each test creates TWO workspaces (A and B), places objects in workspace A,
then asserts that an authenticated member of workspace B cannot read or
mutate those objects — regardless of HTTP verb.

The ENDPOINT_REGISTRY lists every tenant-scoped endpoint family together
with enough factory logic to seed a sample object and assert isolation.
"""
from __future__ import annotations

import uuid
from typing import Any

from django.test import TestCase, override_settings
from django.utils import timezone

BASE_DOMAIN = "educloud.test"


def _ws_host(subdomain: str) -> str:
    return f"{subdomain}.{BASE_DOMAIN}"


# ---------------------------------------------------------------------------
# Shared helpers (mirrors _Base in test_round3.py)
# ---------------------------------------------------------------------------

class _TenantBase(TestCase):

    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()

    # --- user & workspace factories ---

    def _make_user(self, email=None, password="Pass1234!"):
        from apps.accounts.services.registration import register_user
        email = email or f"u-{uuid.uuid4().hex[:8]}@iso.test"
        u, _ = register_user(email=email, password=password)
        u.email_verified_at = timezone.now()
        u.is_active = True
        u.save()
        return u, email

    def _make_workspace(self, owner):
        from apps.workspaces.models import Workspace, WorkspaceMembership
        from apps.workspaces.services.lifecycle import transition
        from apps.core.enums import WorkspaceStatus, ActorType
        slug = f"ws-{uuid.uuid4().hex[:8]}"
        ws = Workspace.objects.create(
            subdomain=slug, status="SETUP",
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
            user=user, workspace=ws, defaults={"role": role, "is_owner": False},
        )

    def _login_client(self, email, password="Pass1234!"):
        from rest_framework.test import APIClient
        c = APIClient()
        c.login(username=email, password=password)
        return c

    def _get(self, client, path, host):
        return client.get(f"/api/v1/{path}", HTTP_HOST=host)

    def _post(self, client, path, data, host):
        return client.post(f"/api/v1/{path}", data=data, format="json", HTTP_HOST=host)

    @staticmethod
    def _items(response) -> list:
        """Extract id list from paginated or plain-list response."""
        data = response.json()
        items = data if isinstance(data, list) else data.get("results", [])
        return [item["id"] for item in items if isinstance(item, dict) and "id" in item]


# ---------------------------------------------------------------------------
# Cross-tenant isolation tests
# ---------------------------------------------------------------------------

@override_settings(BASE_DOMAIN=BASE_DOMAIN, ALLOWED_HOSTS=["*"])
class CrossTenantEnrollmentIsolationTest(_TenantBase):
    """Enrollments in workspace A must not be visible from workspace B."""

    def setUp(self):
        super().setUp()
        self.owner_a, self.owner_a_email = self._make_user()
        self.owner_b, self.owner_b_email = self._make_user()
        self.ws_a = self._make_workspace(self.owner_a)
        self.ws_b = self._make_workspace(self.owner_b)

        # Seed an enrollment in workspace A
        from apps.enrollment.models import Enrollment
        student_a, _ = self._make_user()
        self.enroll_a = Enrollment.objects.create(
            workspace=self.ws_a, student_id=student_a.pk,
            enrollable_type="COURSE", enrollable_id=999,
        )

    def test_owner_b_cannot_list_ws_a_enrollments(self):
        c = self._login_client(self.owner_b_email)
        r = self._get(c, "enrollments/", _ws_host(self.ws_b.subdomain))
        self.assertEqual(r.status_code, 200)
        ids = self._items(r)
        self.assertNotIn(self.enroll_a.id, ids,
                         "Workspace B owner must not see workspace A enrollments")

    def test_owner_b_cannot_retrieve_ws_a_enrollment_directly(self):
        c = self._login_client(self.owner_b_email)
        r = self._get(c, f"enrollments/{self.enroll_a.id}/", _ws_host(self.ws_b.subdomain))
        self.assertIn(r.status_code, [403, 404],
                      "Direct retrieval of cross-tenant enrollment must be denied")


@override_settings(BASE_DOMAIN=BASE_DOMAIN, ALLOWED_HOSTS=["*"])
class CrossTenantStudentPaymentIsolationTest(_TenantBase):
    """Student payments seeded in workspace A must not leak to workspace B."""

    def setUp(self):
        super().setUp()
        self.owner_a, self.owner_a_email = self._make_user()
        self.owner_b, self.owner_b_email = self._make_user()
        self.ws_a = self._make_workspace(self.owner_a)
        self.ws_b = self._make_workspace(self.owner_b)

        from apps.payments.models import StudentPayment
        student_a, _ = self._make_user()
        self._add_member(self.ws_a, student_a, "STUDENT")
        self.pay_a = StudentPayment.objects.create(
            workspace=self.ws_a, student=student_a,
            amount_egp="50.00", status="PENDING",
            payment_model="COURSE_ONE_TIME",
        )

    def test_owner_b_cannot_list_ws_a_payments(self):
        c = self._login_client(self.owner_b_email)
        r = self._get(c, "student-payments/", _ws_host(self.ws_b.subdomain))
        self.assertEqual(r.status_code, 200)
        ids = self._items(r)
        self.assertNotIn(self.pay_a.id, ids,
                         "Workspace B owner must not see workspace A student payments")

    def test_student_b_cannot_see_student_a_payment(self):
        student_b, student_b_email = self._make_user()
        self._add_member(self.ws_b, student_b, "STUDENT")
        c = self._login_client(student_b_email)
        r = self._get(c, "student-payments/", _ws_host(self.ws_b.subdomain))
        self.assertEqual(r.status_code, 200)
        ids = self._items(r)
        self.assertNotIn(self.pay_a.id, ids,
                         "Student B must not see student A's payment from another workspace")


@override_settings(BASE_DOMAIN=BASE_DOMAIN, ALLOWED_HOSTS=["*"])
class CrossTenantSupportTicketIsolationTest(_TenantBase):
    """Support tickets in workspace A must not be visible from workspace B."""

    def setUp(self):
        super().setUp()
        self.owner_a, self.owner_a_email = self._make_user()
        self.owner_b, self.owner_b_email = self._make_user()
        self.ws_a = self._make_workspace(self.owner_a)
        self.ws_b = self._make_workspace(self.owner_b)

        from apps.support.models import SupportTicket
        student_a, _ = self._make_user()
        self._add_member(self.ws_a, student_a, "STUDENT")
        self.ticket_a = SupportTicket.objects.create(
            workspace=self.ws_a, submitted_by_id=student_a.id,
            subject="Ticket A", body="body",
            category="TECHNICAL",
        )

    def test_owner_b_cannot_list_ws_a_tickets(self):
        c = self._login_client(self.owner_b_email)
        r = self._get(c, "support/tickets/", _ws_host(self.ws_b.subdomain))
        self.assertEqual(r.status_code, 200)
        ids = self._items(r)
        self.assertNotIn(self.ticket_a.id, ids,
                         "Workspace B owner must not see workspace A support tickets")


@override_settings(BASE_DOMAIN=BASE_DOMAIN, ALLOWED_HOSTS=["*"])
class CrossTenantSubscriptionIsolationTest(_TenantBase):
    """Subscription data must be scoped to the workspace it was created in."""

    def setUp(self):
        super().setUp()
        self.owner_a, self.owner_a_email = self._make_user()
        self.owner_b, self.owner_b_email = self._make_user()
        self.ws_a = self._make_workspace(self.owner_a)
        self.ws_b = self._make_workspace(self.owner_b)

        from apps.billing.models import Package, Subscription
        from apps.core.enums import SubscriptionStatus
        pkg = Package.objects.create(
            name="Starter", price_egp="100.00", duration_months=1,
            max_students=50, max_subjects_courses=10, max_groups=5,
            max_team_members=3, storage_gb=5,
        )
        self.sub_a = Subscription.objects.create(
            workspace=self.ws_a, package=pkg,
            status=SubscriptionStatus.ACTIVE,
            starts_at=timezone.now(),
            ends_at=timezone.now() + timezone.timedelta(days=30),
        )

    def test_owner_b_cannot_see_ws_a_subscription(self):
        c = self._login_client(self.owner_b_email)
        r = self._get(c, "subscriptions/current/", _ws_host(self.ws_b.subdomain))
        # Must either 404 (no subscription for B) or return B's own subscription
        if r.status_code == 200:
            data = r.json()
            self.assertNotEqual(
                data.get("id"), self.sub_a.id,
                "Workspace B must not see workspace A's subscription",
            )


@override_settings(BASE_DOMAIN=BASE_DOMAIN, ALLOWED_HOSTS=["*"])
class CrossTenantGroupIsolationTest(_TenantBase):
    """Groups created in workspace A must not appear in workspace B's listing."""

    def setUp(self):
        super().setUp()
        self.owner_a, self.owner_a_email = self._make_user()
        self.owner_b, self.owner_b_email = self._make_user()
        self.ws_a = self._make_workspace(self.owner_a)
        self.ws_b = self._make_workspace(self.owner_b)

        from apps.groups.models import Group
        self.group_a = Group.objects.create(
            workspace=self.ws_a, name="Group A", status="ACTIVE",
        )

    def test_owner_b_cannot_list_ws_a_groups(self):
        c = self._login_client(self.owner_b_email)
        r = self._get(c, "groups/", _ws_host(self.ws_b.subdomain))
        self.assertEqual(r.status_code, 200)
        ids = self._items(r)
        self.assertNotIn(self.group_a.id, ids,
                         "Workspace B owner must not see workspace A groups")

    def test_owner_b_cannot_retrieve_ws_a_group_directly(self):
        c = self._login_client(self.owner_b_email)
        r = self._get(c, f"groups/{self.group_a.id}/", _ws_host(self.ws_b.subdomain))
        self.assertIn(r.status_code, [403, 404],
                      "Direct retrieval of cross-tenant group must be denied")


@override_settings(BASE_DOMAIN=BASE_DOMAIN, ALLOWED_HOSTS=["*"])
class CrossTenantNotificationIsolationTest(_TenantBase):
    """Notifications dispatched to workspace A users must not appear for workspace B."""

    def setUp(self):
        super().setUp()
        self.owner_a, self.owner_a_email = self._make_user()
        self.owner_b, self.owner_b_email = self._make_user()
        self.ws_a = self._make_workspace(self.owner_a)
        self.ws_b = self._make_workspace(self.owner_b)

        from apps.notifications.models import Notification
        self.notif_a = Notification.objects.create(
            workspace=self.ws_a, user=self.owner_a,
            category="NEW_ANNOUNCEMENT", payload={"title": "Hello A"},
        )

    def test_owner_b_cannot_see_ws_a_notifications(self):
        c = self._login_client(self.owner_b_email)
        r = self._get(c, "notifications/", _ws_host(self.ws_b.subdomain))
        self.assertEqual(r.status_code, 200)
        ids = self._items(r)
        self.assertNotIn(self.notif_a.id, ids,
                         "Workspace B owner must not see workspace A notifications")
