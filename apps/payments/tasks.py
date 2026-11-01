"""Celery tasks for student payment lifecycle sweeps."""
from celery import shared_task


@shared_task(queue="default")
def flag_overdue_payments():
    """Flag student payments that are PENDING past their period_end date."""
    from django.utils import timezone
    from apps.payments.models import StudentPayment
    from apps.core.enums import StudentPaymentStatus

    today = timezone.localdate()
    count = StudentPayment.objects.filter(
        status=StudentPaymentStatus.PENDING,
        period_end__lt=today,
    ).update(status=StudentPaymentStatus.OVERDUE)
    return count


@shared_task(queue="default")
def remind_pending_payments():
    """
    Send notifications for student payments that are PENDING and approaching due date.
    Fires every 4 hours; targets payments due within 3 days.
    """
    import datetime
    from django.utils import timezone
    from apps.payments.models import StudentPayment
    from apps.core.enums import StudentPaymentStatus, NotificationCategory
    from apps.notifications.services.dispatch import notify

    today = timezone.localdate()
    reminder_horizon = today + datetime.timedelta(days=3)

    pending = StudentPayment.objects.filter(
        status=StudentPaymentStatus.PENDING,
        period_end__lte=reminder_horizon,
        period_end__gte=today,
    ).select_related()

    count = 0
    for payment in pending:
        try:
            notify(
                user_id=payment.student_id,
                workspace_id=payment.workspace_id,
                category=NotificationCategory.PAYMENT_DUE_OR_OVERDUE,
                payload={
                    "payment_id": payment.id,
                    "amount_egp": str(payment.amount_egp),
                    "period_end": str(payment.period_end),
                },
            )
            count += 1
        except Exception:
            pass
    return count


@shared_task(queue="default")
def expire_monthly_course_access():
    """
    Expire StudentCourseAccess records that have passed their expires_at date.
    Runs daily at 7:00 AM Cairo time.
    """
    from django.utils import timezone
    from apps.content.models import StudentCourseAccess

    # Mark expired course access by setting expires_at to a past sentinel
    # (access is expired when expires_at < now — no status column exists)
    from django.db.models import Q
    count = StudentCourseAccess.objects.filter(
        expires_at__isnull=False,
        expires_at__lt=timezone.now(),
    ).count()
    # No mutable status on StudentCourseAccess; the query itself gates access.
    # Return the count of currently-expired records for monitoring.
    return count
    return count
