"""Export registry with allowlists (REQ-RPT-*)."""
from __future__ import annotations

_REGISTRY: dict[str, dict] = {}


def register(name: str, *, model_class, fields: list[str], permission_key: str | None = None):
    _REGISTRY[name] = {
        "model_class": model_class,
        "fields": fields,
        "permission_key": permission_key,
    }


def get(name: str) -> dict:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown export: {name}")
    return _REGISTRY[name]


def list_exports() -> list[str]:
    return list(_REGISTRY.keys())
