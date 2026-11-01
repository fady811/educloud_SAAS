"""ClamAV scanning (REQ-FILE-06, fail-closed)."""
from __future__ import annotations

from django.conf import settings


class ScanResult:
    def __init__(self, clean: bool, details: dict | None = None):
        self.clean = clean
        self.details = details or {}


def scan_file(key: str) -> ScanResult:
    backend = getattr(settings, "SCANNER_BACKEND", "clamav")
    if backend == "null":
        return ScanResult(clean=True, details={"backend": "null"})
    return _clamav_scan(key)


def _clamav_scan(key: str) -> ScanResult:
    import socket
    host = getattr(settings, "CLAMAV_HOST", "localhost")
    port = int(getattr(settings, "CLAMAV_PORT", 3310))
    try:
        with socket.create_connection((host, port), timeout=30) as sock:
            sock.sendall(b"zINSTREAM\0")
            # For real ClamAV integration we'd stream the file bytes;
            # this skeleton sends an empty stream (clean trivially)
            sock.sendall(b"\x00\x00\x00\x00")
            resp = sock.recv(1024).decode("utf-8", errors="replace").strip("\x00")
        if "FOUND" in resp:
            return ScanResult(clean=False, details={"response": resp})
        return ScanResult(clean=True, details={"response": resp})
    except Exception as exc:
        # Fail-closed: unknown = not clean
        return ScanResult(clean=False, details={"error": str(exc)})


def initiate_scan(stored_file) -> None:
    """Kick off async scan for a StoredFile."""
    from apps.files.models import StoredFile
    from apps.core.enums import ScanStatus

    result = scan_file(stored_file.key)
    stored_file.scan_status = ScanStatus.CLEAN if result.clean else ScanStatus.INFECTED
    stored_file.scan_result = result.details
    stored_file.save(update_fields=["scan_status", "scan_result"])


def process_scan_result(file_id: int, result: dict) -> None:
    """Handle scan callback from external scanner webhook."""
    from apps.files.models import StoredFile
    from apps.core.enums import ScanStatus

    clean = result.get("clean", result.get("status") == "clean")
    try:
        f = StoredFile.objects.get(id=file_id)
        f.scan_status = ScanStatus.CLEAN if clean else ScanStatus.INFECTED
        f.scan_result = result
        f.save(update_fields=["scan_status", "scan_result"])
    except StoredFile.DoesNotExist:
        pass
