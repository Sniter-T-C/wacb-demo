from __future__ import annotations

from unittest.mock import patch

import requests
import pytest

from notifiers.base import Notifier
from notifiers.telegram import TelegramNotifier, parse_chat_ids

TOKEN = "123456:fake-token"


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200, raise_error=None):
        self._payload = payload if payload is not None else {"ok": True}
        self.status_code = status_code
        self._raise_error = raise_error

    def raise_for_status(self):
        if self._raise_error is not None:
            raise self._raise_error
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error for url: https://x/bot{TOKEN}/sendMessage")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_parse_chat_ids_strips_dedupes_and_ignores_blanks():
    assert parse_chat_ids(" 1, 2 ,,2, 3 ") == ("1", "2", "3")
    assert parse_chat_ids(["a", " a ", "", "b"]) == ("a", "b")
    assert parse_chat_ids("") == ()


def test_chat_ids_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_IDS", " 111, 222 ,,222 ")
    notifier = TelegramNotifier(token=TOKEN, session=FakeSession([]))

    assert notifier.chat_ids == ("111", "222")


def test_explicit_chat_ids_take_precedence_over_environment(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_IDS", "from-env")
    notifier = TelegramNotifier(token=TOKEN, chat_ids="explicit", session=FakeSession([]))

    assert notifier.chat_ids == ("explicit",)


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        TelegramNotifier(chat_ids="1", session=FakeSession([]))


def test_sends_to_every_chat_even_when_one_fails():
    session = FakeSession(
        [
            FakeResponse({"ok": True}),
            requests.ConnectionError("network down"),
            FakeResponse({"ok": True}),
        ]
    )
    notifier = TelegramNotifier(token=TOKEN, chat_ids="111,222,333", timeout=4.5, session=session)

    results = notifier.send("hola")

    assert [r.recipient for r in results] == ["111", "222", "333"]
    assert [r.ok for r in results] == [True, False, True]
    assert "network down" in results[1].error
    assert [call["json"]["chat_id"] for call in session.calls] == ["111", "222", "333"]
    assert all(call["json"]["text"] == "hola" for call in session.calls)
    assert all(call["timeout"] == 4.5 for call in session.calls)


def test_http_error_is_reported_and_does_not_stop_others():
    session = FakeSession(
        [
            FakeResponse(status_code=500, raise_error=requests.HTTPError("500 Server Error")),
            FakeResponse({"ok": True}),
        ]
    )
    notifier = TelegramNotifier(token=TOKEN, chat_ids="111,222", session=session)

    results = notifier.send("hola")

    assert [r.ok for r in results] == [False, True]
    assert "500 Server Error" in results[0].error
    assert len(session.calls) == 2


def test_api_ok_false_is_reported_as_failure():
    session = FakeSession([FakeResponse({"ok": False, "description": "chat not found"})])
    notifier = TelegramNotifier(token=TOKEN, chat_ids="111", session=session)

    results = notifier.send("hola")

    assert results[0].ok is False
    assert "chat not found" in results[0].error


def test_token_is_redacted_from_errors():
    error = requests.HTTPError(f"403 error for url: https://api.telegram.org/bot{TOKEN}/sendMessage")
    session = FakeSession([FakeResponse(raise_error=error)])
    notifier = TelegramNotifier(token=TOKEN, chat_ids="111", session=session)

    results = notifier.send("hola")

    assert TOKEN not in results[0].error
    assert "<redacted>" in results[0].error


def test_no_chat_ids_means_no_network_calls():
    session = FakeSession([])
    notifier = TelegramNotifier(token=TOKEN, chat_ids="", session=session)

    assert notifier.send("hola") == []
    assert session.calls == []


def test_empty_message_is_rejected():
    notifier = TelegramNotifier(token=TOKEN, chat_ids="111", session=FakeSession([]))

    with pytest.raises(ValueError, match="must not be empty"):
        notifier.send("   ")


def test_endpoint_and_interface():
    notifier = TelegramNotifier(token=TOKEN, chat_ids="111", session=FakeSession([]))

    assert isinstance(notifier, Notifier)
    assert notifier.endpoint == f"https://api.telegram.org/bot{TOKEN}/sendMessage"


def test_default_session_is_patched_at_the_network_layer():
    with patch.object(requests.Session, "post", return_value=FakeResponse({"ok": True})) as post:
        notifier = TelegramNotifier(token=TOKEN, chat_ids="111,222", timeout=7)
        results = notifier.send("hola")

    assert [r.ok for r in results] == [True, True]
    assert post.call_count == 2
    assert all(call.kwargs["timeout"] == 7 for call in post.call_args_list)
