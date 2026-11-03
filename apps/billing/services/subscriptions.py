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

    Same-duration upgrade:
        new_daily   = new_pkg.price_egp / total_days
        charge_base = quantize(new_daily * remaining_days)
        amount_due  = charge_base - credit
        period end does NOT move.

    Duration-change upgrade:
        charge_base = new_pkg.price_egp  (full new term)
        amount_due  = charge_base - credit
        period end  = approval + relativedelta(months=new_pkg.duration_months).
    """
    from apps.billing.models import Package, Subscription, SubscriptionPayment
    from apps.core.errors import Conflict, ValidationFailed
    from apps.core.timeutils import cairo_date
    from dateutil.relativedelta import relativedelta

    old_sub = Subscription.objects.select_related("package").get(id=current_subscription_id)
    if old_sub.status != SubscriptionStatus.ACTIVE:
        raise Conflict("Only ACTIVE subscriptions can be upgraded.", code="SUBSCRIPTION_NOT_FOUND")
    new_pkg = Package.objects.get(id=new_package_id)

    # Capability check: no limit may decrease, no feature may be removed.
    # Price test additionally applies within the same duration.
    _check_upgrade_eligibility(old_sub.package, new_pkg)

    now = timezone.now()
    today = cairo_date()

    # remaining_days uses Cairo business dates (integer days from today to ends_at date).
    ends_at_cairo = old_sub.ends_at.astimezone(
        __import__("pytz").timezone("Africa/Cairo")
    ).date()
    remaining_days = max(Decimal("0"), Decimal(str((ends_at_cairo - today).days)))
    total_days = max(
        Decimal("1"),
        Decimal(str((old_sub.ends_at.date() - old_sub.starts_at.date()).days)),
    )
    credit = (old_sub.package.price_egp / total_days * remaining_days).quantize(Decimal("0.01"))

    same_duration = (old_sub.package.duration_months == new_pkg.duration_months)
    if same_duration:
        # Charge only for the remaining days at the new daily rate.
        new_daily = new_pkg.price_egp / total_days
        charge_base = (new_daily * remaining_days).quantize(Decimal("0.01"))
        new_ends_at = old_sub.ends_at  # period end does not move
    else:
        # Full new term; period end advances.
        charge_base = new_pkg.price_egp
        new_ends_at = now + relativedelta(months=new_pkg.duration_months)
        if new_ends_at < old_sub.ends_at:
            raise ValidationFailed(
                "Upgrade would shorten the coverage period.",
                code="UPGRADE_WOULD_SHORTEN_PERIOD",
            )

    amount_due = (charge_base - credit).quantize(Decimal("0.01"))

    if amount_due < MIN_UPGRADE_CHARGE_EGP:
        from apps.core.enums import ErrorCode
        raise ValidationFailed(
            f"Upgrade charge ({amount_due} EGP) is below minimum ({MIN_UPGRADE_CHARGE_EGP} EGP). "
            f"credit={credit}, charge_base={charge_base}",
            code=ErrorCode.INVALID_UPGRADE_CHARGE,
            details={"credit_egp": str(credit), "charge_base_egp": str(charge_base), "amount_due_egp": str(amount_due)},
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
        "same_duration": same_duration,
        "remaining_days": int(remaining_days),
        "total_days": int(total_days),
        "credit_egp": str(credit),
        "charge_base_egp": str(charge_base),
        "amount_due_egp": str(amount_due),
        "new_ends_at": new_ends_at.isoformat(),
        "current_subscription_id": current_subscription_id,
    }


def _check_upgrade_eligibility(old_pkg, new_pkg) -> None:
    """
    Refuse if any capability is lower or any limit is tighter in the new package.
    Within the same duration, also refuse if price is not strictly higher.
    """
    from apps.core.errors import ValidationFailed

    same_duration = old_pkg.duration_months == new_pkg.duration_months
    if same_duration and new_pkg.price_egp <= old_pkg.price_egp:
        raise ValidationFailed(
            "Cannot upgrade to a cheaper or equal plan within the same duration.",
            code="UPGRADE_NOT_ELIGIBLE",
        )

    # Capability checks: None means unlimited — treat as +∞.
    def _worse(old_val, new_val) -> bool:
        """True if new_val is strictly worse (lower limit) than old_val."""
        if old_val is None:
            return new_val is not None  # old was unlimited, new is limited → worse
        if new_val is None:
            return False  # new is unlimited → not worse
        return new_val < old_val

    checks = [
        ("max_students", old_pkg.max_students, new_pkg.max_students),
        ("max_subjects_courses", old_pkg.max_subjects_courses, new_pkg.max_subjects_courses),
        ("max_groups", old_pkg.max_groups, new_pkg.max_groups),
        ("max_team_members", old_pkg.max_team_members, new_pkg.max_team_members),
        ("storage_gb", old_pkg.storage_gb, new_pkg.storage_gb),
    ]
    for field, old_val, new_val in checks:
        if _worse(old_val, new_val):
            raise ValidationFailed(
                f"New package has a lower {field} limit than the current package.",
                code="UPGRADE_NOT_ELIGIBLE",
            )


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

        from dateutil.relativedelta import relativedelta as _rd
        new_ends_at_str = quote["new_ends_at"]
        # Parse the ISO string stored in the quote (already computed correctly).
        from django.utils.dateparse import parse_datetime
        import dateutil.parser as _dparser
        new_ends_at = _dparser.isoparse(new_ends_at_str)

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
