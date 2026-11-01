"""Tenant context — contextvar holder, admin_context(), get_current_workspace() (§15.2)."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator

_workspace_var: ContextVar[int | None] = ContextVar("workspace_id", default=None)
_admin_context_var: ContextVar[bool] = ContextVar("admin_context", default=False)


def set_current_workspace(workspace_id: int | None) -> None:
    _workspace_var.set(workspace_id)


def get_current_workspace_id() -> int | None:
    return _workspace_var.get()


def is_admin_context() -> bool:
    return _admin_context_var.get()


@contextmanager
def admin_context(workspace_id: int) -> Generator[None, None, None]:
    """
    The ONLY sanctioned way to access cross-tenant data (INV-03, §15.4).
    Emits an audit row on entry — callers must pass actor info via audit.record().
    """
    prev_ws = _workspace_var.get()
    prev_admin = _admin_context_var.get()
    _workspace_var.set(workspace_id)
    _admin_context_var.set(True)
    try:
        yield
    finally:
        _workspace_var.set(prev_ws)
        _admin_context_var.set(prev_admin)
