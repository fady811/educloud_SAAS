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


MIN_UPGRADE_CHARGE_EGP = Decimal("1.00")


def get_upgrade_quote(current_subscription_id: int, new_package_id: int) -> dict:
    """
    Compute upgrade proration quote without writing anything.
    Validates all business rules and returns the quote dict.
    """
    from apps.billing.models import Package, Subscription, SubscriptionPayment
    from apps.core.errors import Conflict, ValidationFailed

    old_sub = Subscription.objects.select_related("package").get(id=current_subscription_id)
    if old_sub.status != SubscriptionStatus.ACTIVE:
        raise Conflict("Only ACTIVE subscriptions can be upgraded.", code="SUBSCRIPTION_NOT_FOUND")
    new_pkg = Package.objects.get(id=new_package_id)

    # Must not downgrade
    if new_pkg.price_egp <= old_sub.package.price_egp:
        raise ValidationFailed(
            "Cannot upgrade to a cheaper or equal plan.",
            code="UPGRADE_NOT_ELIGIBLE",
        )

    now = timezone.now()
    remaining_days = max(Decimal("0"), Decimal(str((old_sub.ends_at - now).days)))
    total_days = max(Decimal("1"), Decimal(str((old_sub.ends_at - old_sub.starts_at).days)))
    credit = (old_sub.package.price_egp / total_days * remaining_days).quantize(Decimal("0.01"))

    # Determine new end date
    same_duration = (old_sub.package.duration_months == new_pkg.duration_months)
    if same_duration:
        new_ends_at = old_sub.ends_at  # period end does not move
    else:
        new_ends_at = now + datetime.timedelta(days=30 * new_pkg.duration_months)

    # New end must not be earlier than current
    if new_ends_at < old_sub.ends_at and not same_duration:
        raise ValidationFailed(
            "Upgrade would shorten the coverage period.",
            code="UPGRADE_WOULD_SHORTEN_PERIOD",
        )

    amount_due = max(Decimal("0"), new_pkg.price_egp - credit)
    if amount_due < MIN_UPGRADE_CHARGE_EGP and amount_due > Decimal("0"):
        raise ValidationFailed(
            f"Upgrade charge ({amount_due} EGP) is below minimum ({MIN_UPGRADE_CHARGE_EGP} EGP).",
            code="UPGRADE_MIN_CHARGE",
        )

    # Check no pending renewal
    pending_renewal = SubscriptionPayment.objects.filter(
        workspace_id=old_sub.workspace_id,
        kind=SubPaymentKind.RENEWAL,
        status__in=[SubPaymentStatus.SUBMITTED, SubPaymentStatus.UNDER_REVIEW],
    ).exists()
    if pending_renewal:
        raise Conflict("A scheduled renewal already exists.", code="PAYMENT_PENDING")

    return {
        "old_package_id": old_sub.package.id,
        "new_package_id": new_pkg.id,
        "remaining_days": int(remaining_days),
        "credit_egp": str(credit),
        "amount_due_egp": str(amount_due),
        "new_ends_at": new_ends_at.isoformat(),
        "current_subscription_id": current_subscription_id,
    }


def prorate_upgrade(
    current_subscription_id: int,
    new_package_id: int,
    *,
    actor_id: int,
    quoted_amount: Decimal | None = None,
) -> "Subscription":
    """DR-036/DR-037: proration on plan upgrade with all business-rule validations."""
    from apps.billing.models import Package, Subscription, SubscriptionPayment
    from django.db.models import F

    with transaction.atomic():
        old_sub = Subscription.objects.select_for_update().select_related("package").get(
            id=current_subscription_id
        )
        new_pkg = Package.objects.get(id=new_package_id)

        # Re-validate inside the transaction (quote may have gone stale)
        quote = get_upgrade_quote(current_subscription_id, new_package_id)
        amount_due = Decimal(quote["amount_due_egp"])

        if quoted_amount is not None:
            if abs(quoted_amount - amount_due) > Decimal("0.01"):
                from apps.core.errors import Conflict
                raise Conflict(
                    "Upgrade quote is stale — re-fetch and resubmit.",
                    code="QUOTE_STALE",
                )

        same_duration = (old_sub.package.duration_months == new_pkg.duration_months)
        if same_duration:
            new_ends_at = old_sub.ends_at
        else:
            new_ends_at = timezone.now() + datetime.timedelta(days=30 * new_pkg.duration_months)

        # Supersede old subscription (do not mutate snapshot — INV-27)
        old_sub.status = SubscriptionStatus.SUPERSEDED
        old_sub.save(update_fields=["status", "updated_at"])

        credit = Decimal(quote["credit_egp"])
        new_sub = Subscription.objects.create(
            workspace_id=old_sub.workspace_id,
            package=new_pkg,
            status=SubscriptionStatus.SCHEDULED,
            starts_at=timezone.now(),
            ends_at=new_ends_at,
            previous_subscription_id=old_sub.id,
            proration_credit_egp=credit,
        )
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


def purchase_addon(
    *,
    workspace_id: int,
    addon_type: str,
    quantity: int,
    price_egp: Decimal,
    proof_file_id: int | None = None,
    actor_id: int,
) -> "CapacityAddon":
    """Purchase a capacity add-on (student slots or storage)."""
    from apps.billing.models import CapacityAddon
    from apps.core.enums import AddonStatus

    with transaction.atomic():
        addon = CapacityAddon.objects.create(
            workspace_id=workspace_id,
            addon_type=addon_type,
            quantity=quantity,
            price_egp=price_egp,
            status=AddonStatus.PENDING,
            proof_file_id=proof_file_id,
        )
        audit.record(
            actor_id=actor_id,
            actor_type=ActorType.USER,
            action="ADDON_PURCHASED",
            target_type="CapacityAddon",
            target_id=addon.id,
            workspace_id=workspace_id,
            after={"addon_type": addon_type, "quantity": quantity, "price_egp": str(price_egp)},
        )
    return addon
