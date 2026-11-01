"""Storage backends: R2 (production) and local (tests)."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

from django.conf import settings


class StorageBackend(ABC):
    @abstractmethod
    def presign_upload(self, key: str, content_type: str, size_bytes: int) -> dict:
        ...

    @abstractmethod
    def issue_download_url(self, key: str, filename: str, expires: int = 3600) -> str:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...


class R2Backend(StorageBackend):
    def __init__(self):
        import boto3
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        self._bucket = settings.R2_BUCKET_NAME

    def presign_upload(self, key: str, content_type: str, size_bytes: int) -> dict:
        url = self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": size_bytes,
            },
            ExpiresIn=900,
        )
        return {"url": url, "key": key, "method": "PUT"}

    def issue_download_url(self, key: str, filename: str, expires: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=expires,
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False


class LocalBackend(StorageBackend):
    """Dev/test backend — stores under MEDIA_ROOT."""

    def presign_upload(self, key: str, content_type: str, size_bytes: int) -> dict:
        return {"url": f"/dev-upload/{key}", "key": key, "method": "PUT"}

    def issue_download_url(self, key: str, filename: str, expires: int = 3600) -> str:
        return f"/media/{key}"

    def delete(self, key: str) -> None:
        path = os.path.join(settings.MEDIA_ROOT, key)
        if os.path.exists(path):
            os.remove(path)

    def exists(self, key: str) -> bool:
        return os.path.exists(os.path.join(settings.MEDIA_ROOT, key))


def get_storage() -> StorageBackend:
    backend = getattr(settings, "STORAGE_BACKEND", "r2")
    if backend == "local":
        return LocalBackend()
    return R2Backend()


# ── Convenience module-level helpers ────────────────────────────────────────
def delete_object(key: str) -> None:
    get_storage().delete(key)


def object_exists(key: str) -> bool:
    return get_storage().exists(key)


def get_presigned_url(key: str, filename: str = "", expires: int = 3600) -> str:
    return get_storage().issue_download_url(key, filename or key.rsplit("/", 1)[-1], expires)
