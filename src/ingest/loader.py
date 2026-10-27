"""Carga y validacion del JSON de alertas mock."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MOCK_LABEL = "MOCK"
ALARM_WINDOW = timedelta(hours=48)

REQUIRED_TOP_LEVEL = ("dataset", "alerts")
REQUIRED_DATASET = ("name", "version", "label", "generated_at", "disclaimer")
REQUIRED_ALERT = (
    "alert_id",
    "label",
    "typology",
    "detected_at",
    "deadline_48h",
    "score",
    "confidence",
    "subject",
    "onchain",
    "modus_operandi",
    "recommended_actions",
)
REQUIRED_SUBJECT = ("entity", "jurisdiction", "risk_flags")
REQUIRED_ONCHAIN = ("chains", "addresses", "transactions", "total_volume_usd")
REQUIRED_ADDRESS = ("address", "chain", "role")
REQUIRED_TRANSACTION = (
    "hash",
    "chain",
    "asset",
    "amount",
    "usd_value",
    "direction",
    "timestamp",
    "counterparty",
)
REQUIRED_MODUS_OPERANDI = ("summary", "stages", "red_flags")


class AlertValidationError(ValueError):
    """Error agregado con todos los problemas de validacion encontrados."""

    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = tuple(errors)
        detail = "\n".join(f"- {error}" for error in self.errors)
        super().__init__(f"JSON de alertas invalido:\n{detail}")


def load_dataset(path: str | Path) -> dict[str, Any]:
    """Lee, parsea y valida un archivo de alertas."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"No existe el archivo de alertas: {source}")

    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AlertValidationError(
            [f"JSON invalido: {exc.msg} (linea {exc.lineno}, columna {exc.colno})."]
        ) from exc

    validate_dataset(data)
    return data


def load_alerts(path: str | Path) -> list[dict[str, Any]]:
    """Devuelve solo la lista de alertas de un archivo validado."""
    return load_dataset(path)["alerts"]


def validate_dataset(data: Any) -> None:
    """Valida el documento completo y lanza AlertValidationError si falla."""
    if not isinstance(data, dict):
        raise AlertValidationError(["La raiz del documento debe ser un objeto JSON."])

    errors: list[str] = []
    _require_keys(data, REQUIRED_TOP_LEVEL, "raiz", errors)

    if "dataset" in data:
        dataset = data["dataset"]
        if not isinstance(dataset, dict):
            errors.append("dataset: debe ser un objeto JSON.")
        else:
            _validate_dataset_metadata(dataset, errors)

    if "alerts" in data:
        alerts = data["alerts"]
        if not isinstance(alerts, list) or not alerts:
            errors.append("alerts: debe ser una lista con al menos una alerta.")
        else:
            seen_ids: set[str] = set()
            for index, alert in enumerate(alerts):
                prefix = f"alerts[{index}]"
                if not isinstance(alert, dict):
                    errors.append(f"{prefix}: debe ser un objeto JSON.")
                    continue
                _validate_alert(alert, prefix, errors, seen_ids)

    if errors:
        raise AlertValidationError(errors)


def _validate_dataset_metadata(dataset: Mapping[str, Any], errors: list[str]) -> None:
    _require_keys(dataset, REQUIRED_DATASET, "dataset", errors)

    for key in ("name", "version", "disclaimer"):
        _string_field(dataset, key, "dataset", errors)

    label = _string_field(dataset, "label", "dataset", errors)
    if label is not None and label != MOCK_LABEL:
        errors.append(
            f"dataset.label: debe ser {MOCK_LABEL!r} para descartar datos no ficticios."
        )

    _timestamp_field(dataset, "generated_at", "dataset", errors)


def _validate_alert(
    alert: Mapping[str, Any],
    prefix: str,
    errors: list[str],
    seen_ids: set[str],
) -> None:
    _require_keys(alert, REQUIRED_ALERT, prefix, errors)

    alert_id = _string_field(alert, "alert_id", prefix, errors)
    if alert_id is not None:
        if alert_id in seen_ids:
            errors.append(f"{prefix}.alert_id: identificador duplicado ({alert_id!r}).")
        seen_ids.add(alert_id)

    label = _string_field(alert, "label", prefix, errors)
    if label is not None and label != MOCK_LABEL:
        errors.append(f"{prefix}.label: debe ser {MOCK_LABEL!r}.")

    _string_field(alert, "typology", prefix, errors)
    _number_field(alert, "score", prefix, errors, minimum=1, maximum=100, integer=True)
    _number_field(alert, "confidence", prefix, errors, minimum=0, maximum=1)

    detected_at = _timestamp_field(alert, "detected_at", prefix, errors)
    deadline = _timestamp_field(alert, "deadline_48h", prefix, errors)
    if detected_at is not None and deadline is not None:
        if deadline != detected_at + ALARM_WINDOW:
            errors.append(
                f"{prefix}.deadline_48h: debe ser exactamente 48 h despues de detected_at."
            )

    subject = _object_field(alert, "subject", prefix, errors, REQUIRED_SUBJECT)
    if subject is not None:
        _validate_subject(subject, f"{prefix}.subject", errors)

    onchain = _object_field(alert, "onchain", prefix, errors, REQUIRED_ONCHAIN)
    if onchain is not None:
        _validate_onchain(onchain, f"{prefix}.onchain", errors)

    modus = _object_field(
        alert, "modus_operandi", prefix, errors, REQUIRED_MODUS_OPERANDI
    )
    if modus is not None:
        _validate_modus_operandi(modus, f"{prefix}.modus_operandi", errors)

    _string_list_field(alert, "recommended_actions", prefix, errors)
    if "narrative" in alert:
        _string_field(alert, "narrative", prefix, errors)


def _validate_subject(
    subject: Mapping[str, Any], path: str, errors: list[str]
) -> None:
    _string_field(subject, "entity", path, errors)
    _string_field(subject, "jurisdiction", path, errors)
    _string_list_field(subject, "risk_flags", path, errors)


def _validate_onchain(
    onchain: Mapping[str, Any], path: str, errors: list[str]
) -> None:
    _string_list_field(onchain, "chains", path, errors)
    _number_field(onchain, "total_volume_usd", path, errors, minimum=0)

    addresses = onchain.get("addresses")
    if not isinstance(addresses, list) or not addresses:
        errors.append(f"{path}.addresses: debe ser una lista con al menos una direccion.")
    else:
        for index, address in enumerate(addresses):
            address_path = f"{path}.addresses[{index}]"
            if not isinstance(address, dict):
                errors.append(f"{address_path}: debe ser un objeto JSON.")
                continue
            _require_keys(address, REQUIRED_ADDRESS, address_path, errors)
            for key in REQUIRED_ADDRESS:
                _string_field(address, key, address_path, errors)
            if "risk" in address:
                _string_field(address, "risk", address_path, errors)

    transactions = onchain.get("transactions")
    if not isinstance(transactions, list) or not transactions:
        errors.append(
            f"{path}.transactions: debe ser una lista con al menos una transaccion."
        )
    else:
        for index, transaction in enumerate(transactions):
            tx_path = f"{path}.transactions[{index}]"
            if not isinstance(transaction, dict):
                errors.append(f"{tx_path}: debe ser un objeto JSON.")
                continue
            _require_keys(transaction, REQUIRED_TRANSACTION, tx_path, errors)
            for key in ("hash", "chain", "asset", "direction", "counterparty"):
                _string_field(transaction, key, tx_path, errors)
            _number_field(transaction, "amount", tx_path, errors, minimum=0)
            _number_field(transaction, "usd_value", tx_path, errors, minimum=0)
            _timestamp_field(transaction, "timestamp", tx_path, errors)

    if "notes" in onchain:
        _string_field(onchain, "notes", path, errors)


def _validate_modus_operandi(
    modus: Mapping[str, Any], path: str, errors: list[str]
) -> None:
    _string_field(modus, "summary", path, errors)
    _string_list_field(modus, "stages", path, errors)
    _string_list_field(modus, "red_flags", path, errors)


def _require_keys(
    data: Mapping[str, Any],
    keys: Sequence[str],
    path: str,
    errors: list[str],
) -> None:
    for key in keys:
        if key not in data:
            errors.append(f"{path}.{key}: campo obligatorio ausente.")


def _string_field(
    data: Mapping[str, Any], key: str, path: str, errors: list[str]
) -> str | None:
    if key not in data:
        return None
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}.{key}: debe ser una cadena no vacia.")
        return None
    return value


def _string_list_field(
    data: Mapping[str, Any], key: str, path: str, errors: list[str]
) -> list[str] | None:
    if key not in data:
        return None
    value = data[key]
    if not isinstance(value, list) or not value:
        errors.append(f"{path}.{key}: debe ser una lista no vacia.")
        return None
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{path}.{key}[{index}]: debe ser una cadena no vacia.")
    return value


def _number_field(
    data: Mapping[str, Any],
    key: str,
    path: str,
    errors: list[str],
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    integer: bool = False,
) -> int | float | None:
    if key not in data:
        return None
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{path}.{key}: debe ser un numero.")
        return None
    if integer and not isinstance(value, int):
        errors.append(f"{path}.{key}: debe ser un entero.")
        return None
    if minimum is not None and value < minimum:
        errors.append(f"{path}.{key}: debe ser mayor o igual a {minimum}.")
    if maximum is not None and value > maximum:
        errors.append(f"{path}.{key}: debe ser menor o igual a {maximum}.")
    return value


def _timestamp_field(
    data: Mapping[str, Any], key: str, path: str, errors: list[str]
) -> datetime | None:
    value = _string_field(data, key, path, errors)
    if value is None:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{path}.{key}: timestamp ISO 8601 invalido ({value!r}).")
        return None

    if parsed.tzinfo is None:
        errors.append(f"{path}.{key}: el timestamp debe incluir zona horaria.")
        return None

    return parsed.astimezone(timezone.utc)


def _object_field(
    data: Mapping[str, Any],
    key: str,
    path: str,
    errors: list[str],
    required_keys: Sequence[str],
) -> Mapping[str, Any] | None:
    if key not in data:
        return None
    value = data[key]
    if not isinstance(value, dict):
        errors.append(f"{path}.{key}: debe ser un objeto JSON.")
        return None
    _require_keys(value, required_keys, f"{path}.{key}", errors)
    return value
