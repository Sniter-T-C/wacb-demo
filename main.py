from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv

from src.enrichment.mock_enricher import MockEnricher
from src.ingest.loader import load_dataset
from src.notifiers.telegram import TelegramNotifier
from src.reporting.dossier import write_dossier

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DATA_DIR = BASE_DIR / "data"
DEFAULT_DATASET = DATA_DIR / "mock_alerts.json"

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
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to the mock alerts JSON file.",
    )
    demo.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory where generated dossiers are written.",
    )
    demo.add_argument(
        "--skip-notify",
        action="store_true",
        help="Generate dossiers without sending Telegram notifications.",
    )

    return parser


def check_environment() -> dict[str, bool]:
    return {name: bool(os.getenv(name)) for name in REQUIRED_ENV_VARS}


def build_notification(alert: Mapping[str, Any], dossier_path: Path) -> str:
    enrichment = alert.get("enrichment") or {}
    subject = alert.get("subject") or {}
    remaining = enrichment.get("hours_to_deadline")
    if remaining is None:
        deadline_state = "desconocido"
    elif remaining > 0:
        deadline_state = f"quedan {remaining} h"
    else:
        deadline_state = f"vencida hace {abs(remaining)} h"

    return "\n".join(
        [
            "WACB — Nueva alerta MOCK",
            f"ID: {alert.get('alert_id')}",
            f"Tipología: {alert.get('typology')}",
            f"Score: {alert.get('score')}/100 ({enrichment.get('risk_band', '—')})",
            f"Entidad: {subject.get('entity', '—')}",
            f"Jurisdicción: {subject.get('jurisdiction', '—')}",
            f"Ventana 48 h: {deadline_state}",
            f"Dossier: {dossier_path}",
            "",
            "Datos ficticios (MOCK). Requiere revisión humana.",
        ]
    )


def _dossier_filename(alert: Mapping[str, Any]) -> str:
    alert_id = str(alert.get("alert_id") or "alert")
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", alert_id).strip("._") or "alert"
    return f"{safe_id}.md"


def _notify(artifacts: list[tuple[dict[str, Any], Path]]) -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_ids = os.getenv("TELEGRAM_CHAT_IDS", "").strip()
    if not token or not chat_ids:
        logger.error(
            "Telegram no está configurado: define TELEGRAM_BOT_TOKEN y "
            "TELEGRAM_CHAT_IDS, o ejecuta con --skip-notify."
        )
        return 1

    notifier = TelegramNotifier(token=token, chat_ids=chat_ids)
    failures = 0
    for alert, dossier_path in artifacts:
        results = notifier.send(build_notification(alert, dossier_path))
        if not results:
            logger.warning("No hay destinatarios de Telegram configurados.")
            continue
        for result in results:
            if result.ok:
                logger.info("Notificación enviada a %s.", result.recipient)
            else:
                failures += 1
                logger.error(
                    "Falló la notificación a %s: %s", result.recipient, result.error
                )

    return 1 if failures else 0


def run_demo(
    output_dir: Path,
    skip_notify: bool,
    dataset_path: Path = DEFAULT_DATASET,
) -> int:
    dataset = load_dataset(dataset_path)
    alerts = dataset["alerts"]
    metadata = dataset.get("dataset")

    output_dir.mkdir(parents=True, exist_ok=True)
    enricher = MockEnricher()

    artifacts: list[tuple[dict[str, Any], Path]] = []
    for raw_alert in alerts:
        alert = enricher.enrich(raw_alert)
        dossier_path = write_dossier(
            alert,
            output_dir / _dossier_filename(alert),
            dataset=metadata,
        )
        artifacts.append((alert, dossier_path))
        logger.info(
            "Dossier generado para %s: %s", alert.get("alert_id"), dossier_path
        )

    logger.info("%d dossier(s) generados en %s.", len(artifacts), output_dir)

    if skip_notify:
        logger.info("Notificación de Telegram omitida (--skip-notify).")
        return 0

    return _notify(artifacts)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    load_dotenv(BASE_DIR / ".env")

    if args.command == "demo":
        try:
            return run_demo(args.output_dir, args.skip_notify, args.dataset)
        except (FileNotFoundError, ValueError) as exc:
            logger.error("%s", exc)
            return 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
