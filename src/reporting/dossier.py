"""Generacion del dossier Markdown para alertas mock."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..ingest.loader import ALARM_WINDOW, MOCK_LABEL, REQUIRED_ALERT

DEFAULT_DISCLAIMER = (
    "MOCK: todos los nombres, direcciones, transacciones y entidades son ficticios. "
    "No corresponden a personas, organizaciones ni fondos reales."
)


def build_dossier(
    alert: Mapping[str, Any],
    dataset: Mapping[str, Any] | None = None,
    as_of: str | datetime | None = None,
) -> str:
    """Construye el informe Markdown completo para una alerta ficticia."""
    if not isinstance(alert, Mapping):
        raise ValueError("La alerta debe ser un objeto con campos de compliance.")

    missing = [key for key in REQUIRED_ALERT if key not in alert]
    if missing:
        raise ValueError("Alerta incompleta: faltan " + ", ".join(missing) + ".")

    if alert["label"] != MOCK_LABEL:
        raise ValueError("Solo se pueden generar dossiers para alertas con etiqueta MOCK.")

    score = alert["score"]
    if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 100:
        raise ValueError("El score debe ser un entero entre 1 y 100.")

    detected_at = _parse_datetime(alert["detected_at"], "detected_at")
    deadline = _parse_datetime(alert["deadline_48h"], "deadline_48h")
    if deadline != detected_at + ALARM_WINDOW:
        raise ValueError(
            "deadline_48h debe ser exactamente 48 h despues de detected_at."
        )

    reference = _parse_datetime(as_of, "as_of") if as_of is not None else detected_at
    remaining = deadline - reference
    if remaining.total_seconds() > 0:
        alarm_state = f"**ACTIVA** — quedan {_format_hours(remaining)} h"
    else:
        alarm_state = f"**VENCIDA** — {_format_hours(-remaining)} h desde el vencimiento"

    subject = alert["subject"]
    onchain = alert["onchain"]
    modus = alert["modus_operandi"]
    band = _score_band(score)
    disclaimer = DEFAULT_DISCLAIMER
    if dataset and dataset.get("disclaimer"):
        disclaimer = str(dataset["disclaimer"])

    lines: list[str] = [
        f"# Dossier de alerta — {alert['alert_id']}",
        "",
        f"> **{alert['label']} — DATOS FICTICIOS.** {disclaimer}",
        "",
        "## 1. Metadatos",
        "",
        "| Campo | Valor |",
        "| --- | --- |",
        f"| ID de alerta | `{_cell(alert['alert_id'])}` |",
        f"| Etiqueta | **{_cell(alert['label'])}** |",
        f"| Tipología | `{_cell(alert['typology'])}` |",
        f"| Confianza | {_format_confidence(alert['confidence'])} |",
        f"| Sujeto | {_cell(subject.get('entity'))} |",
        f"| Jurisdicción | {_cell(subject.get('jurisdiction'))} |",
        f"| Dataset | {_dataset_label(dataset)} |",
        f"| Generado | {_dataset_timestamp(dataset)} |",
        f"| Ventana de análisis | {_fmt_datetime(detected_at)} → {_fmt_datetime(deadline)} |",
        "",
        "## 2. Alarma de 48 h",
        "",
        "| Campo | Valor |",
        "| --- | --- |",
        f"| Detección | {_fmt_datetime(detected_at)} |",
        f"| Vencimiento | {_fmt_datetime(deadline)} |",
        f"| Referencia | {_fmt_datetime(reference)} |",
        f"| Estado | {alarm_state} |",
        "| Ventana | 48 h desde la detección |",
        f"| Score | {score}/100 ({band}) |",
        "",
        "## 3. Resumen on-chain (MOCK)",
        "",
        "> Importes, direcciones, hashes y transacciones ficticios. No usar para "
        "investigación real.",
        "",
        f"- **Cadenas:** {_join(onchain.get('chains'))}",
        f"- **Volumen observado:** {_format_usd(onchain.get('total_volume_usd'))}",
        f"- **Direcciones:** {len(onchain.get('addresses') or [])} · "
        f"**Transacciones:** {len(onchain.get('transactions') or [])}",
        "",
        "### Direcciones",
        "",
        "| # | Dirección | Cadena | Rol | Riesgo |",
        "| --- | --- | --- | --- | --- |",
    ]

    for index, address in enumerate(onchain.get("addresses") or [], start=1):
        lines.append(
            f"| {index} | `{_cell(address.get('address'))}` | "
            f"{_cell(address.get('chain'))} | {_cell(address.get('role'))} | "
            f"{_cell(address.get('risk', 'no informado'))} |"
        )

    lines.extend(
        [
            "",
            "### Transacciones",
            "",
            "| # | Hash | Cadena | Activo | Importe | Valor USD | Dirección | Fecha |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for index, transaction in enumerate(onchain.get("transactions") or [], start=1):
        lines.append(
            f"| {index} | `{_cell(transaction.get('hash'))}` | "
            f"{_cell(transaction.get('chain'))} | {_cell(transaction.get('asset'))} | "
            f"{_format_number(transaction.get('amount'))} | "
            f"{_format_usd(transaction.get('usd_value'))} | "
            f"{_cell(transaction.get('direction'))} | "
            f"{_format_timestamp_value(transaction.get('timestamp'))} |"
        )

    if onchain.get("notes"):
        lines.extend(["", f"_{onchain['notes']}_"])

    lines.extend(
        [
            "",
            "## 4. Modus Operandi",
            "",
        ]
    )

    if alert.get("narrative"):
        lines.extend([f"> {alert['narrative']}", ""])

    lines.extend(
        [
            f"**Resumen.** {modus.get('summary', 'No informado.')}",
            "",
            "### Etapas observadas",
            "",
        ]
    )
    for index, stage in enumerate(modus.get("stages") or [], start=1):
        lines.append(f"{index}. {stage}")

    lines.extend(["", "### Señales de alerta", ""])
    for red_flag in modus.get("red_flags") or []:
        lines.append(f"- {red_flag}")

    filled = min(20, max(1, round(score / 5)))
    bar = "█" * filled + "░" * (20 - filled)
    lines.extend(
        [
            "",
            "## 5. Score de riesgo (1-100)",
            "",
            f"**{score}/100 — {band}**",
            "",
            f"`{bar}`",
            "",
            "Escala: 1-20 Bajo · 21-50 Medio · 51-75 Alto · 76-100 Crítico.",
            "",
            "## 6. Recomendación operativa",
            "",
        ]
    )
    for index, action in enumerate(alert["recommended_actions"], start=1):
        lines.append(f"{index}. {action}")

    lines.extend(
        [
            "",
            "> Las medidas anteriores son propuestas MOCK y requieren validación de "
            "compliance/legal antes de su ejecución.",
            "",
            "## 7. Aviso de alcance",
            "",
            "> **MOCK — Datos ficticios.** Este dossier se genera a partir de un "
            "conjunto de datos de demostración y no describe un caso real.",
            ">",
            "> No constituye asesoramiento legal, financiero ni una acusación. Las "
            "direcciones y entidades mencionadas son ficticias.",
            ">",
            "> El score y las recomendaciones son insumos preliminares. La "
            "clasificación final, el escalado y cualquier medida sobre activos "
            "quedan sujetos a **revisión y decisión humana** por parte de un "
            "analista de compliance.",
            "",
            "---",
            "_Generado por B-dossier en modo MOCK._",
            "",
        ]
    )

    return "\n".join(lines)


def write_dossier(
    alert: Mapping[str, Any],
    output_path: str | Path,
    dataset: Mapping[str, Any] | None = None,
    as_of: str | datetime | None = None,
) -> Path:
    """Genera el dossier y lo escribe en disco, creando carpetas si hace falta."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = build_dossier(alert, dataset=dataset, as_of=as_of)
    destination.write_text(content, encoding="utf-8", newline="\n")
    return destination


def _score_band(score: int) -> str:
    if score <= 20:
        return "Bajo"
    if score <= 50:
        return "Medio"
    if score <= 75:
        return "Alto"
    return "Crítico"


def _parse_datetime(value: Any, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field}: timestamp ISO 8601 invalido ({value!r}).") from exc
    else:
        raise ValueError(f"{field}: se esperaba un timestamp ISO 8601.")

    if parsed.tzinfo is None:
        raise ValueError(f"{field}: el timestamp debe incluir zona horaria.")
    return parsed.astimezone(UTC)


def _format_timestamp_value(value: Any) -> str:
    if not value:
        return "—"
    try:
        return _fmt_datetime(_parse_datetime(value, "timestamp"))
    except ValueError:
        return _cell(value)


def _fmt_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _format_hours(value: timedelta) -> str:
    return f"{value.total_seconds() / 3600:.1f}".rstrip("0").rstrip(".")


def _format_confidence(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _cell(value)
    return f"{value:.0%}"


def _format_number(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _cell(value)
    return f"{value:,.2f}"


def _format_usd(value: Any) -> str:
    number = _format_number(value)
    if number == "—":
        return number
    return f"${number} USD"


def _join(values: Any) -> str:
    if isinstance(values, (list, tuple)) and values:
        return ", ".join(str(value) for value in values)
    return "—"


def _dataset_label(dataset: Mapping[str, Any] | None) -> str:
    if not dataset:
        return "No especificado"
    name = dataset.get("name")
    version = dataset.get("version")
    if name and version:
        return f"{name} v{version}"
    return _cell(name or "No especificado")


def _dataset_timestamp(dataset: Mapping[str, Any] | None) -> str:
    if not dataset or not dataset.get("generated_at"):
        return "—"
    return _format_timestamp_value(dataset["generated_at"])


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")
