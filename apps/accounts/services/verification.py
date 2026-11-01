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
        vt.user.is_active = True
        vt.user.save(update_fields=["is_active"])
