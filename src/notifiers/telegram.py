"""Telegram notifier built on top of the Bot API via ``requests``."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from typing import Any

import requests

from .base import DeliveryResult, Notifier

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://api.telegram.org"
DEFAULT_TIMEOUT = 10.0


class TelegramError(RuntimeError):
    """Raised when the Bot API answers with ``ok: false``."""


def parse_chat_ids(raw: str | Iterable[str]) -> tuple[str, ...]:
    """Normalize a comma-separated string or iterable of chat ids."""

    if isinstance(raw, str):
        parts = raw.split(",")
    else:
        parts = raw

    chat_ids: list[str] = []
    seen: set[str] = set()
    for part in parts:
        chat_id = str(part).strip()
        if chat_id and chat_id not in seen:
            seen.add(chat_id)
            chat_ids.append(chat_id)
    return tuple(chat_ids)


class TelegramNotifier(Notifier):
    """Send messages to a list of Telegram chats.

    The chat list is read from ``TELEGRAM_CHAT_IDS`` (comma separated) unless
    it is passed explicitly. The bot token is read from
    ``TELEGRAM_BOT_TOKEN`` unless passed explicitly.
    """

    def __init__(
        self,
        token: str | None = None,
        chat_ids: str | Iterable[str] | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        api_base: str = DEFAULT_API_BASE,
        session: requests.Session | None = None,
    ) -> None:
        self.token = (token if token is not None else os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
        if not self.token:
            raise ValueError(
                "A Telegram bot token is required: pass token=... or set TELEGRAM_BOT_TOKEN."
            )

        raw_chat_ids = chat_ids if chat_ids is not None else os.getenv("TELEGRAM_CHAT_IDS", "")
        self.chat_ids = parse_chat_ids(raw_chat_ids)
        self.timeout = timeout
        self.api_base = api_base.rstrip("/")
        self._session = session or requests.Session()

    @property
    def endpoint(self) -> str:
        return f"{self.api_base}/bot{self.token}/sendMessage"

    def send(self, message: str) -> list[DeliveryResult]:
        if not message or not message.strip():
            raise ValueError("The message must not be empty.")

        if not self.chat_ids:
            logger.warning("TELEGRAM_CHAT_IDS is empty; nothing to send.")
            return []

        results: list[DeliveryResult] = []
        for chat_id in self.chat_ids:
            try:
                self._send_one(chat_id, message)
            except Exception as exc:  # noqa: BLE001 - one failure must not stop the rest
                error = self._safe_error(exc)
                logger.warning("Telegram delivery to %s failed: %s", chat_id, error)
                results.append(DeliveryResult(recipient=chat_id, ok=False, error=error))
            else:
                results.append(DeliveryResult(recipient=chat_id, ok=True))
        return results

    def _send_one(self, chat_id: str, message: str) -> None:
        response = self._session.post(
            self.endpoint,
            json={"chat_id": chat_id, "text": message},
            timeout=self.timeout,
        )
        response.raise_for_status()

        payload: Any = response.json()
        if not isinstance(payload, dict) or not payload.get("ok", False):
            description = "unknown error"
            if isinstance(payload, dict):
                description = str(payload.get("description") or description)
            raise TelegramError(f"Telegram API rejected the message: {description}")

    def _safe_error(self, exc: Exception) -> str:
        text = str(exc) or exc.__class__.__name__
        if self.token:
            text = text.replace(self.token, "<redacted>")
        return text
