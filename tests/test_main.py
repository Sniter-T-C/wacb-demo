from __future__ import annotations

from pathlib import Path

from main import build_parser, check_environment, main


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
    assert tmp_path.is_dir()


def test_check_environment_reports_expected_keys() -> None:
    status = check_environment()
    assert set(status) == {"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_IDS", "ETHERSCAN_API_KEY"}
