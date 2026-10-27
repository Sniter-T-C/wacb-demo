from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_license_is_present() -> None:
    assert (ROOT / "LICENSE").is_file()


def test_secret_scanning_config_is_present() -> None:
    assert (ROOT / ".gitleaks.toml").is_file()


def test_env_example_is_tracked_and_env_is_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert (ROOT / ".env.example").is_file()
    assert ".env" in gitignore
    assert "!.env.example" in gitignore
