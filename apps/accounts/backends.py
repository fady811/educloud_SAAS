"""EmailOrPhoneAuthBackend (§5.1.3, C-04)."""
from __future__ import annotations

from typing import Any

from django.contrib.auth.backends import ModelBackend

from apps.core.validators import normalize_phone


class EmailOrPhoneAuthBackend(ModelBackend):
    """Authenticate by email OR phone, globally unique (INV-07)."""

    def authenticate(
        self,
        request: Any,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> "User | None":  # type: ignore[name-defined]
        from apps.accounts.models import User

        if not username or not password:
            return None

        user = None
        # Try email
        if "@" in username:
            user = User.objects.filter(email__iexact=username, deleted_at__isnull=True).first()
        else:
            # Try normalized phone
            phone = normalize_phone(username)
            user = User.objects.filter(phone=phone, deleted_at__isnull=True).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
