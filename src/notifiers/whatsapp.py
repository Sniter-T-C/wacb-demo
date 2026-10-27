"""WhatsApp notifier placeholder."""

from __future__ import annotations

from .base import DeliveryResult, Notifier


class WhatsAppNotifier(Notifier):
    """Not implemented yet; kept so providers can be swapped uniformly."""

    def send(self, message: str) -> list[DeliveryResult]:
        raise NotImplementedError("WhatsApp notifications are not implemented yet.")
