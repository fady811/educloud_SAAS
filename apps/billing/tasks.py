"""Celery tasks for billing lifecycle sweeps."""
from celery import shared_task


@shared_task(queue="default")
def expire_subscriptions():
    """Mark past-due active subscriptions as expired and trigger grace period."""
    from django.utils import timezone
    from apps.billing.models import Subscription
    from apps.billing.services.subscriptions import expire_subscription
    from apps.core.enums import SubscriptionStatus

    expired_ids = list(
        Subscription.objects.filter(
            status=SubscriptionStatus.ACTIVE,
            ends_at__lt=timezone.now(),
        ).values_list("id", flat=True)
    )
    for sub_id in expired_ids:
        try:
            expire_subscription(sub_id)
        except Exception:
            pass
    return len(expired_ids)


@shared_task(queue="default")
def expire_addons():
    from django.utils import timezone
    from apps.billing.models import CapacityAddon
    from apps.core.enums import AddonStatus

    count = CapacityAddon.objects.filter(
        status=AddonStatus.ACTIVE,
        expires_at__lt=timezone.now(),
    ).update(status=AddonStatus.EXPIRED)
    return count


@shared_task(queue="default")
def flag_overdue_payments():
    """Flag subscription payments that are past-due."""
    from django.utils import timezone
    from apps.billing.models import SubscriptionPayment
    from apps.core.enums import SubPaymentStatus
    import datetime

    cutoff = timezone.now() - datetime.timedelta(days=7)
    count = SubscriptionPayment.objects.filter(
        status=SubPaymentStatus.SUBMITTED,
        created_at__lt=cutoff,
    ).update(status=SubPaymentStatus.REJECTED)
    return count
