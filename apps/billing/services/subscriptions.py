"""Subscription lifecycle: activate, expire, upgrade proration (REQ-SUB-02..14)."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.enums import ActorType, SubPaymentKind, SubPaymentStatus, SubscriptionStatus
from apps.core import audit


def create_subscription(*, workspace_id: int, package_id: int, actor_id: int | None = None) -> "Subscription":
    from apps.billing.models import Package, Subscription, SubscriptionPayment

    with transaction.atomic():
        pkg = Package.objects.select_for_update().get(id=package_id)
        starts_at = timezone.now()
        ends_at = starts_at + datetime.timedelta(days=30 * pkg.duration_months)

        sub = Subscription.objects.create(
            workspace_id=workspace_id,
            package=pkg,
            status=SubscriptionStatus.SCHEDULED,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        SubscriptionPayment.objects.create(
            workspace_id=workspace_id,
            subscription=sub,
            kind=SubPaymentKind.NEW_SUBSCRIPTION,
            amount_egp=pkg.price_egp,
            status=SubPaymentStatus.SUBMITTED,
        )
        audit.record(
            actor_id=actor_id,
            actor_type=ActorType.USER if actor_id else ActorType.SYSTEM,
            action="SUBSCRIPTION_CREATED",
            target_type="Subscription",
            target_id=sub.id,
            workspace_id=workspace_id,
            after={"package": pkg.slug, "ends_at": ends_at.isoformat()},
        )
    return sub


def activate_subscription(subscription_id: int, *, actor_id: int) -> "Subscription":
    from apps.billing.models import Subscription

    with transaction.atomic():
        sub = Subscription.objects.select_for_update().get(id=subscription_id)
        if sub.status == SubscriptionStatus.ACTIVE:
            return sub
        _snapshot = _build_snapshot(sub.package)
        sub.status = SubscriptionStatus.ACTIVE
        sub.entitlement_snapshot = _snapshot
        sub.save(update_fields=["status", "entitlement_snapshot", "updated_at"])
        audit.record(
            actor_id=actor_id,
            actor_type=ActorType.ADMIN,
            action="SUBSCRIPTION_ACTIVATED",
            target_type="Subscription",
            target_id=sub.id,
            workspace_id=sub.workspace_id,
        )
    return sub


def expire_subscription(subscription_id: int) -> None:
    from apps.billing.models import Subscription

    with transaction.atomic():
        sub = Subscription.objects.select_for_update().get(id=subscription_id)
        if sub.status != SubscriptionStatus.ACTIVE:
            return
        sub.status = SubscriptionStatus.EXPIRED
        sub.save(update_fields=["status", "updated_at"])
        _trigger_grace_period(sub.workspace_id)


def _trigger_grace_period(workspace_id: int) -> None:
    from apps.workspaces.models import Workspace
    from apps.workspaces.services.lifecycle import transition
    from apps.core.enums import WorkspaceStatus

    try:
        ws = Workspace.objects.get(id=workspace_id)
        if ws.status == WorkspaceStatus.ACTIVE:
            transition(ws, WorkspaceStatus.GRACE_PERIOD, reason="subscription_expired")
    except Exception:
        pass


def _build_snapshot(package) -> dict:
    return {
        "package_id": package.id,
        "package_slug": package.slug,
        "max_students": package.max_students,
        "storage_gb": float(package.storage_gb) if package.storage_gb else None,
        "max_subjects_courses": package.max_subjects_courses,
        "max_groups": package.max_groups,
        "max_team_members": package.max_team_members,
    }


def prorate_upgrade(
    current_subscription_id: int,
    new_package_id: int,
    *,
    actor_id: int,
) -> "Subscription":
    """DR-036/DR-037: proration on plan upgrade."""
    from apps.billing.models import Package, Subscription, SubscriptionPayment

    with transaction.atomic():
        old_sub = Subscription.objects.select_for_update().get(id=current_subscription_id)
        new_pkg = Package.objects.get(id=new_package_id)

        now = timezone.now()
        remaining = (old_sub.ends_at - now).total_seconds()
        total = (old_sub.ends_at - old_sub.starts_at).total_seconds()
        ratio = max(Decimal("0"), Decimal(str(remaining / total if total > 0 else 0)))
        credit = (old_sub.package.price_egp * ratio).quantize(Decimal("0.01"))

        # Expire old
        old_sub.status = SubscriptionStatus.EXPIRED
        old_sub.save(update_fields=["status", "updated_at"])

        starts_at = now
        ends_at = starts_at + datetime.timedelta(days=30 * new_pkg.duration_months)
        new_sub = Subscription.objects.create(
            workspace_id=old_sub.workspace_id,
            package=new_pkg,
            status=SubscriptionStatus.SCHEDULED,
            starts_at=starts_at,
            ends_at=ends_at,
            previous_subscription_id=old_sub.id,
            proration_credit_egp=credit,
        )
        amount_due = max(Decimal("0"), new_pkg.price_egp - credit)
        SubscriptionPayment.objects.create(
            workspace_id=old_sub.workspace_id,
            subscription=new_sub,
            kind=SubPaymentKind.UPGRADE,
            amount_egp=amount_due,
            status=SubPaymentStatus.SUBMITTED,
        )
        audit.record(
            actor_id=actor_id,
            actor_type=ActorType.USER,
            action="SUBSCRIPTION_UPGRADED",
            target_type="Subscription",
            target_id=new_sub.id,
            workspace_id=old_sub.workspace_id,
            after={"credit_egp": str(credit), "amount_due": str(amount_due)},
        )
    return new_sub
