"""Account async tasks."""
from __future__ import annotations

from celery import shared_task


@shared_task(queue="high", bind=True, max_retries=3)
def send_verification_email(self, user_id: int, token_id: int) -> None:
    """Send account verification email/SMS."""
    from apps.accounts.models import User, VerificationToken
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        user = User.objects.get(id=user_id)
        token = VerificationToken.objects.get(id=token_id)
        if user.email and not user.email_verified_at:
            send_mail(
                subject="Verify your EduCloud account",
                message=f"Please verify your account. Token: {token.token_hash[:8]}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(queue="high", bind=True, max_retries=3)
def send_password_reset_email(self, user_id: int, token_id: int) -> None:
    from apps.accounts.models import User, PasswordResetToken
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        user = User.objects.get(id=user_id)
        token = PasswordResetToken.objects.get(id=token_id)
        if user.email:
            send_mail(
                subject="Reset your EduCloud password",
                message=f"Use this token to reset your password: {token.token_hash[:8]}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
