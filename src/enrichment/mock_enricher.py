"""Mock enrichment for the demo's MOCK alerts."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

RISK_BANDS = (
    (20, "Low"),
    (50, "Medium"),
    (75, "High"),
    (100, "Critical"),
)


def risk_band(score: int) -> str:
    """Return the risk band associated with a 1-100 score."""
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
            raise ValueError(f"{field}: invalid ISO 8601 timestamp ({value!r}).") from exc
    else:
        raise ValueError(f"{field}: an ISO 8601 timestamp was expected.")

    if parsed.tzinfo is None:
        raise ValueError(f"{field}: the timestamp must include a timezone.")
    return parsed.astimezone(UTC)


class MockEnricher:
    """Add derived context to an alert without querying external sources.

    The result keeps every original field and adds an ``enrichment`` block with
    the risk band, the 48 h window state and aggregated on-chain metrics.
    """

    provider = "mock"

    def __init__(self, as_of: str | datetime | None = None) -> None:
        self.as_of = (
            _parse_timestamp(as_of, "as_of")
            if as_of is not None
            else datetime.now(UTC)
        )

    def enrich(self, alert: Mapping[str, Any]) -> dict[str, Any]:
        enriched = copy.deepcopy(dict(alert))

        score = alert.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 100:
            raise ValueError("The score must be an integer between 1 and 100.")

        detected_at = _parse_timestamp(alert.get("detected_at"), "detected_at")
        deadline = _parse_timestamp(alert.get("deadline_48h"), "deadline_48h")

        remaining_hours = round((deadline - self.as_of).total_seconds() / 3600, 1)
        onchain = alert.get("onchain") or {}

        enriched["enrichment"] = {
            "provider": self.provider,
            "as_of": self.as_of.isoformat().replace("+00:00", "Z"),
            "risk_band": risk_band(score),
            "alarm_status": "active" if remaining_hours > 0 else "expired",
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
