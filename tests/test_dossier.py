import copy
from pathlib import Path

import pytest

from src.ingest.loader import load_dataset
from src.reporting.dossier import build_dossier, write_dossier

MOCK_PATH = Path(__file__).resolve().parents[1] / "data" / "mock_alerts.json"

HEADINGS = [
    "## 1. Metadatos",
    "## 2. Alarma de 48 h",
    "## 3. Resumen on-chain (MOCK)",
    "## 4. Modus Operandi",
    "## 5. Score de riesgo (1-100)",
    "## 6. Recomendación operativa",
    "## 7. Aviso de alcance",
]


@pytest.fixture()
def payload():
    return load_dataset(MOCK_PATH)


@pytest.fixture()
def alert(payload):
    return copy.deepcopy(payload["alerts"][0])


def test_dossier_contains_master_document_sections(payload, alert):
    markdown = build_dossier(alert, payload["dataset"])

    for heading in HEADINGS:
        assert heading in markdown


def test_dossier_includes_scope_notice_with_human_decision(payload, alert):
    markdown = build_dossier(alert, payload["dataset"])

    assert "decisión humana" in markdown
    assert "MOCK" in markdown
    assert "No constituye asesoramiento legal" in markdown


def test_dossier_renders_alert_metadata_and_score(payload, alert):
    markdown = build_dossier(alert, payload["dataset"])

    assert "MOCK-PB-2026-0001" in markdown
    assert "pig_butchering" in markdown
    assert "86%" in markdown
    assert "87/100" in markdown
    assert "Crítico" in markdown


def test_dossier_renders_mock_onchain_summary(payload, alert):
    markdown = build_dossier(alert, payload["dataset"])

    assert "$412,500.00 USD" in markdown
    assert "0xMOCK000000000000000000000000000000000A1" in markdown
    assert "0xmock-tx-0001" in markdown
    assert "MOCK-TRC20" in markdown


def test_dossier_renders_modus_operandi_and_recommendations(payload, alert):
    markdown = build_dossier(alert, payload["dataset"])

    assert "### Etapas observadas" in markdown
    assert "### Señales de alerta" in markdown
    assert "Evaluar el congelamiento preventivo" in markdown


def test_dossier_48h_alarm_is_active_with_default_reference(payload, alert):
    markdown = build_dossier(alert, payload["dataset"])

    assert "ACTIVA" in markdown
    assert "quedan 48 h" in markdown


def test_dossier_48h_alarm_is_expired_with_custom_as_of(payload, alert):
    markdown = build_dossier(
        alert, payload["dataset"], as_of="2026-10-30T09:00:00Z"
    )

    assert "VENCIDA" in markdown
    assert "24 h desde el vencimiento" in markdown


def test_dossier_48h_alarm_counts_remaining_hours(payload, alert):
    markdown = build_dossier(
        alert, payload["dataset"], as_of="2026-10-29T03:00:00Z"
    )

    assert "quedan 6 h" in markdown


@pytest.mark.parametrize("score", [0, 101, True, 87.5])
def test_dossier_rejects_out_of_range_score(payload, alert, score):
    alert["score"] = score

    with pytest.raises(ValueError, match="1 y 100"):
        build_dossier(alert, payload["dataset"])


def test_dossier_rejects_non_mock_label(payload, alert):
    alert["label"] = "REAL"

    with pytest.raises(ValueError, match="MOCK"):
        build_dossier(alert, payload["dataset"])


def test_dossier_rejects_invalid_48h_window(payload, alert):
    alert["deadline_48h"] = "2026-10-28T09:00:00Z"

    with pytest.raises(ValueError, match="48 h"):
        build_dossier(alert, payload["dataset"])


def test_dossier_rejects_incomplete_alert(payload, alert):
    alert.pop("score")

    with pytest.raises(ValueError, match="Alerta incompleta"):
        build_dossier(alert, payload["dataset"])


def test_write_dossier_creates_parent_directories(tmp_path, payload, alert):
    destination = tmp_path / "reports" / "dossier.md"

    written = write_dossier(alert, destination, payload["dataset"])

    assert written == destination
    assert destination.is_file()
    assert destination.read_text(encoding="utf-8") == build_dossier(
        alert, payload["dataset"]
    )


def test_dossier_is_deterministic(payload, alert):
    first = build_dossier(alert, payload["dataset"])
    second = build_dossier(alert, payload["dataset"])

    assert first == second
