"""Common interfaces for notification providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    """Outcome of a delivery attempt to a single recipient."""

    recipient: str
    ok: bool
    error: str | None = None


class Notifier(ABC):
    """Interface implemented by every notification provider."""

    @abstractmethod
    def send(self, message: str) -> list[DeliveryResult]:
        """Deliver ``message`` to every configured recipient.

        Implementations must attempt every recipient even when some of them
        fail, and return one result per recipient.
        """
