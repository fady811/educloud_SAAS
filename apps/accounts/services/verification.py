"""Email/phone verification flows."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.core.errors import ValidationFailed


def verify_token(token: str) -> None:
    import hashlib
    from apps.accounts.models import VerificationToken

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with transaction.atomic():
        try:
            vt = VerificationToken.objects.select_for_update().get(
                token_hash=token_hash,
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
        except VerificationToken.DoesNotExist:
            raise ValidationFailed("Invalid or expired token.", code="INVALID_TOKEN")
        vt.used_at = timezone.now()
        vt.save(update_fields=["used_at"])
        user = vt.user
        user.is_active = True
        if vt.purpose == "email_verification":
            user.email_verified_at = timezone.now()
            user.save(update_fields=["is_active", "email_verified_at"])
        else:
            user.phone_verified_at = timezone.now()
            user.save(update_fields=["is_active", "phone_verified_at"])


def resend_verification(user: object) -> "VerificationToken":  # type: ignore[name-defined]
    """Issue a new verification token for the user (invalidates old ones implicitly via expiry)."""
    import hashlib
    import secrets
    from datetime import timedelta
    from django.conf import settings
    from apps.accounts.models import VerificationToken

    if getattr(user, "email", None):
        purpose = "email_verification"
    else:
        purpose = "phone_activation"

    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expiry = timezone.now() + timedelta(seconds=getattr(settings, "VERIFICATION_TOKEN_EXPIRY", 86400))

    vt = VerificationToken.objects.create(
        user=user,
        token_hash=token_hash,
        purpose=purpose,
        expires_at=expiry,
    )
    vt._raw_token = raw  # type: ignore[attr-defined]
    return vt
