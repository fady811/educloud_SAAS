from __future__ import annotations

class InAppChannel:
    name = "in_app"
    def deliver(self, notification: object) -> None:
        # In-app delivery is the act of writing the Notification row itself.
        pass
