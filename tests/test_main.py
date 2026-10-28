from __future__ import annotations

from pathlib import Path

import main as cli
from main import build_parser, check_environment, main
from src.notifiers.base import DeliveryResult


def test_parser_requires_command() -> None:
    parser = build_parser()
    try:
        parser.parse_args([])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("parser should require a command")


def test_demo_runs_and_creates_output(tmp_path: Path) -> None:
    exit_code = main(["demo", "--output-dir", str(tmp_path), "--skip-notify"])
    assert exit_code == 0
    dossier = tmp_path / "MOCK-PB-2026-0001.md"
    assert dossier.is_file()
    assert "MOCK-PB-2026-0001" in dossier.read_text(encoding="utf-8")


def test_check_environment_reports_expected_keys() -> None:
    status = check_environment()
    assert set(status) == {"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_IDS", "ETHERSCAN_API_KEY"}


def test_demo_sends_telegram_notification(tmp_path: Path, monkeypatch) -> None:
    sent: list[str] = []

    class FakeTelegramNotifier:
        def __init__(self, *, token: str, chat_ids: str) -> None:
            assert token == "fake-token"
            assert chat_ids == "123"

        def send(self, message: str) -> list[DeliveryResult]:
            sent.append(message)
            return [DeliveryResult(recipient="123", ok=True)]

    monkeypatch.setattr(cli, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "TelegramNotifier", FakeTelegramNotifier)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_IDS", "123")

    exit_code = main(["demo", "--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert len(sent) == 1
    assert "MOCK-PB-2026-0001" in sent[0]


def test_demo_fails_without_telegram_credentials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_IDS", raising=False)

    exit_code = main(["demo", "--output-dir", str(tmp_path)])

    assert exit_code == 1
    assert (tmp_path / "MOCK-PB-2026-0001.md").is_file()
