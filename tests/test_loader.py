import copy
from pathlib import Path

import pytest

from src.ingest.loader import (
    AlertValidationError,
    load_alerts,
    load_dataset,
    validate_dataset,
)

MOCK_PATH = Path(__file__).resolve().parents[1] / "data" / "mock_alerts.json"


@pytest.fixture()
def dataset():
    return load_dataset(MOCK_PATH)


def test_load_dataset_returns_mock_pig_butchering_alert(dataset):
    assert dataset["dataset"]["label"] == "MOCK"
    assert len(dataset["alerts"]) == 1

    alert = dataset["alerts"][0]
    assert alert["label"] == "MOCK"
    assert alert["typology"] == "pig_butchering"
    assert alert["subject"]["entity"].endswith("(MOCK)")
    assert alert["onchain"]["total_volume_usd"] == pytest.approx(412500.0)
    assert alert["score"] == 87


def test_load_alerts_returns_only_alert_list(dataset):
    assert load_alerts(MOCK_PATH) == dataset["alerts"]


def test_validate_dataset_accepts_valid_payload(dataset):
    assert validate_dataset(dataset) is None


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda data: data.pop("dataset"), "dataset"),
        (lambda data: data["alerts"][0].pop("alert_id"), "alert_id"),
        (lambda data: data["alerts"][0].pop("onchain"), "onchain"),
        (lambda data: data["alerts"][0].pop("recommended_actions"), "recommended_actions"),
        (lambda data: data["alerts"][0].__setitem__("label", "REAL"), "MOCK"),
        (lambda data: data["dataset"].__setitem__("label", "REAL"), "MOCK"),
        (lambda data: data["alerts"][0].__setitem__("score", 0), "score"),
        (lambda data: data["alerts"][0].__setitem__("score", 101), "score"),
        (lambda data: data["alerts"][0].__setitem__("score", 87.5), "entero"),
        (lambda data: data["alerts"][0].__setitem__("confidence", 1.5), "confidence"),
        (
            lambda data: data["alerts"][0].__setitem__(
                "deadline_48h", "2026-10-28T09:00:00Z"
            ),
            "48 h",
        ),
        (
            lambda data: data["alerts"][0]["onchain"].pop("total_volume_usd"),
            "total_volume_usd",
        ),
        (
            lambda data: data["alerts"][0]["onchain"]["transactions"][0].pop("hash"),
            "hash",
        ),
        (
            lambda data: data["alerts"][0]["modus_operandi"].__setitem__(
                "red_flags", []
            ),
            "red_flags",
        ),
        (
            lambda data: data["alerts"][0].__setitem__(
                "detected_at", "2026-10-27T09:00:00"
            ),
            "zona horaria",
        ),
        (lambda data: data.__setitem__("alerts", []), "alerts"),
        (
            lambda data: data["alerts"].append(copy.deepcopy(data["alerts"][0])),
            "duplicado",
        ),
    ],
)
def test_validate_dataset_rejects_invalid_payload(dataset, mutate, expected):
    mutate(dataset)

    with pytest.raises(AlertValidationError) as excinfo:
        validate_dataset(dataset)

    assert expected in str(excinfo.value)
    assert excinfo.value.errors


def test_validate_dataset_rejects_non_object_root():
    with pytest.raises(AlertValidationError, match="raiz"):
        validate_dataset(["no", "es", "un", "objeto"])


def test_load_dataset_rejects_malformed_json(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{esto no es json", encoding="utf-8")

    with pytest.raises(AlertValidationError, match="JSON invalido"):
        load_dataset(broken)


def test_load_dataset_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_dataset(tmp_path / "no-existe.json")
