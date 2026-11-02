"""Password reset flow."""
from __future__ import annotations

import hashlib
import secrets

from django.db import transaction
from django.utils import timezone

from apps.core.errors import ValidationFailed


def request_reset(*, identifier: str) -> str:
    import datetime
    from apps.accounts.models import PasswordResetToken, User

    user = None
    if "@" in identifier:
        user = User.objects.filter(email=identifier).first()
    else:
        from apps.core.validators import normalize_phone
        phone = normalize_phone(identifier)
        user = User.objects.filter(phone=phone).first()

    if not user:
        return ""  # Silent: don't reveal whether the account exists

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    PasswordResetToken.objects.create(
        user=user,
        token_hash=token_hash,
        expires_at=timezone.now() + datetime.timedelta(hours=2),
    )
    return raw_token


def confirm_reset(*, token: str, new_password: str) -> None:
    from apps.accounts.models import PasswordResetToken, UserSession

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with transaction.atomic():
        try:
            prt = PasswordResetToken.objects.select_for_update().get(
                token_hash=token_hash,
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
        except PasswordResetToken.DoesNotExist:
            raise ValidationFailed("Invalid or expired token.", code="INVALID_TOKEN")
        prt.user.set_password(new_password)
        prt.user.save(update_fields=["password"])
        prt.used_at = timezone.now()
        prt.save(update_fields=["used_at"])
        # Revoke all active sessions so stolen-token attacks can't persist access
        UserSession.objects.filter(user=prt.user, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
