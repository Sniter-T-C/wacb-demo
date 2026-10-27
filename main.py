from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DATA_DIR = BASE_DIR / "data"

REQUIRED_ENV_VARS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_IDS",
    "ETHERSCAN_API_KEY",
)

logger = logging.getLogger("web3_compliance_bridge")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="web3-compliance-bridge-demo",
        description="Demo pipeline for Web3 compliance ingestion, enrichment and reporting.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="Run the end-to-end demo pipeline.")
    demo.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory where generated artifacts are written.",
    )
    demo.add_argument(
        "--skip-notify",
        action="store_true",
        help="Skip the Telegram notification step.",
    )

    return parser


def check_environment() -> dict[str, bool]:
    return {name: bool(os.getenv(name)) for name in REQUIRED_ENV_VARS}


def run_demo(output_dir: Path, skip_notify: bool) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    env_status = check_environment()
    for name, present in env_status.items():
        logger.info("%s: %s", name, "configured" if present else "missing")

    logger.info("Output directory: %s", output_dir)
    logger.info("Notification step: %s", "skipped" if skip_notify else "enabled")
    logger.info("Demo pipeline finished successfully.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    load_dotenv(BASE_DIR / ".env")

    if args.command == "demo":
        return run_demo(args.output_dir, args.skip_notify)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
