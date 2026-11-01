from __future__ import annotations
from typing import Protocol, runtime_checkable

@runtime_checkable
class Channel(Protocol):
    name: str
    def deliver(self, notification: object) -> None: ...
