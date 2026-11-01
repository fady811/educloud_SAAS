"""
Metrics facade with no-op backend (DR-040, INV-117).
Callers use this; the backend is swapped by settings.METRICS_BACKEND.
"""
from __future__ import annotations

from typing import Callable


class _NoOpBackend:
    def counter(self, name: str, value: int = 1, **labels: str) -> None:
        pass

    def histogram(self, name: str, value: float, **labels: str) -> None:
        pass

    def gauge(self, name: str, value: float, **labels: str) -> None:
        pass


_backend = _NoOpBackend()

# Closed name registry — prevents metric name drift
_REGISTERED_METRICS: set[str] = {
    "api.requests.total",
    "api.request.duration_ms",
    "workspace.lifecycle.transitions",
    "subscription.activations",
    "enrollment.created",
    "exam.attempts.started",
    "exam.attempts.submitted",
    "files.uploaded.bytes",
    "files.scanned.total",
    "celery.task.duration_ms",
}


def counter(name: str, value: int = 1, **labels: str) -> None:
    _assert_registered(name)
    _backend.counter(name, value, **labels)


def histogram(name: str, value: float, **labels: str) -> None:
    _assert_registered(name)
    _backend.histogram(name, value, **labels)


def gauge(name: str, value: float, **labels: str) -> None:
    _assert_registered(name)
    _backend.gauge(name, value, **labels)


def _assert_registered(name: str) -> None:
    if name not in _REGISTERED_METRICS:
        raise ValueError(f"Metric {name!r} is not in the closed registry (INV-117).")
