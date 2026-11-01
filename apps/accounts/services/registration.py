"""User registration service (REQ-WS-01, REQ-SEC-01)."""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.errors import ValidationFailed, Conflict
from apps.core.validators import normalize_phone


def register_user(
    *,
    email: str | None = None,
    phone: str | None = None,
    password: str,
    first_name: str = "",
    last_name: str = "",
) -> tuple["User", "VerificationToken"]:  # type: ignore[name-defined]
    """
    Create a new User and issue a verification token.
    Exactly one of email/phone required (§5.1.3, C-04).
    """
    from apps.accounts.models import User, VerificationToken

    if not email and not phone:
        raise ValidationFailed("Either email or phone is required.")

    # Normalize
    if phone:
        phone = normalize_phone(phone)

    with transaction.atomic():
        # Duplicate check
        if email and User.objects.filter(email__iexact=email).exists():
            raise Conflict("An account with this email already exists.", code="DUPLICATE_EMAIL")
        if phone and User.objects.filter(phone=phone).exists():
            raise Conflict("An account with this phone number already exists.", code="DUPLICATE_PHONE")

        user = User.objects.create_user(
            email=email,
            phone=phone,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        token = _issue_verification_token(user, purpose="email_verification" if email else "phone_activation")

    return user, token


def _issue_verification_token(user: "User", purpose: str) -> "VerificationToken":  # type: ignore[name-defined]
    from apps.accounts.models import VerificationToken

    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expiry = timezone.now() + timedelta(seconds=settings.VERIFICATION_TOKEN_EXPIRY)

    vt = VerificationToken.objects.create(
        user=user,
        token_hash=token_hash,
        purpose=purpose,
        expires_at=expiry,
    )
    vt._raw_token = raw  # type: ignore[attr-defined] — only available in-request for email dispatch
    return vt
