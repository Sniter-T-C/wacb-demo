"""Enriquecimiento simulado para las alertas MOCK de la demo."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Mapping

RISK_BANDS = (
    (20, "Bajo"),
    (50, "Medio"),
    (75, "Alto"),
    (100, "Crítico"),
)


def risk_band(score: int) -> str:
    """Devuelve la banda de riesgo asociada a un score 1-100."""
    for upper_bound, label in RISK_BANDS:
        if score <= upper_bound:
            return label
    return RISK_BANDS[-1][1]


def _parse_timestamp(value: Any, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field}: timestamp ISO 8601 inválido ({value!r}).") from exc
    else:
        raise ValueError(f"{field}: se esperaba un timestamp ISO 8601.")

    if parsed.tzinfo is None:
        raise ValueError(f"{field}: el timestamp debe incluir zona horaria.")
    return parsed.astimezone(timezone.utc)


class MockEnricher:
    """Añade contexto derivado a una alerta sin consultar fuentes externas.

    El resultado conserva todos los campos originales y agrega un bloque
    ``enrichment`` con la banda de riesgo, el estado de la ventana de 48 h y
    métricas on-chain agregadas.
    """

    provider = "mock"

    def __init__(self, as_of: str | datetime | None = None) -> None:
        self.as_of = (
            _parse_timestamp(as_of, "as_of")
            if as_of is not None
            else datetime.now(timezone.utc)
        )

    def enrich(self, alert: Mapping[str, Any]) -> dict[str, Any]:
        enriched = copy.deepcopy(dict(alert))

        score = alert.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 100:
            raise ValueError("El score debe ser un entero entre 1 y 100.")

        detected_at = _parse_timestamp(alert.get("detected_at"), "detected_at")
        deadline = _parse_timestamp(alert.get("deadline_48h"), "deadline_48h")

        remaining_hours = round((deadline - self.as_of).total_seconds() / 3600, 1)
        onchain = alert.get("onchain") or {}

        enriched["enrichment"] = {
            "provider": self.provider,
            "as_of": self.as_of.isoformat().replace("+00:00", "Z"),
            "risk_band": risk_band(score),
            "alarm_status": "activa" if remaining_hours > 0 else "vencida",
            "hours_to_deadline": remaining_hours,
            "detected_at": detected_at.isoformat().replace("+00:00", "Z"),
            "deadline_48h": deadline.isoformat().replace("+00:00", "Z"),
            "chains": list(onchain.get("chains") or []),
            "address_count": len(onchain.get("addresses") or []),
            "transaction_count": len(onchain.get("transactions") or []),
            "total_volume_usd": onchain.get("total_volume_usd"),
            "human_review_required": True,
        }
        return enriched

    def enrich_many(self, alerts: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [self.enrich(alert) for alert in alerts]
