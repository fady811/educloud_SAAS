"""Idempotency-Key store and decorator (§16.5)."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any, Callable

from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class IdempotencyKey(TimeStampedModel):
    """Persists idempotency keys to prevent duplicate operations."""

    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    result_status = models.SmallIntegerField()
    result_body = models.JSONField(default=dict)
    expires_at = models.DateTimeField()

    class Meta:
        app_label = "core"
        db_table = "idempotency_keys"

    @classmethod
    def hash_key(cls, key: str, user_id: int, path: str) -> str:
        payload = f"{key}:{user_id}:{path}"
        return hashlib.sha256(payload.encode()).hexdigest()

    @classmethod
    def get_or_none(cls, key_hash: str) -> "IdempotencyKey | None":
        return cls.objects.filter(key_hash=key_hash, expires_at__gt=timezone.now()).first()

    @classmethod
    def store(cls, key_hash: str, status: int, body: Any, ttl_seconds: int = 86400) -> None:
        cls.objects.update_or_create(
            key_hash=key_hash,
            defaults={
                "result_status": status,
                "result_body": body,
                "expires_at": timezone.now() + timedelta(seconds=ttl_seconds),
            },
        )
