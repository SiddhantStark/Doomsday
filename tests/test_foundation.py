import json
import logging
from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from doomsday.cli import load_results, main, preview
from doomsday.config import Config, load_config
from doomsday.logging_utils import RedactingFormatter
from doomsday.models import ProviderResult

CONFIG = Path("config/monitor.yml")
FIXTURE = Path("tests/fixtures/preview.json")


def test_schedule_and_bookable_sorting() -> None:
    config = load_config(CONFIG)
    assert config.monitor.interval_on(date(2026, 9, 28)) == 1440
    assert config.monitor.interval_on(date(2026, 11, 5)) == 360
    assert config.monitor.interval_on(date(2026, 12, 18)) == 60
    output = preview(load_results(FIXTURE, config), config)
    assert len(output["intended_events"]) == 1
    assert output["intended_events"][0]["first_show"] == "09:00:00"


@pytest.mark.parametrize(
    "mutation", ["paid", "frequency", "unknown", "retry", "providers"]
)
def test_invalid_configuration(mutation: str) -> None:
    raw = yaml.safe_load(CONFIG.read_text())
    if mutation == "paid":
        raw["notifications"]["allow_paid_broadcast"] = True
    elif mutation == "frequency":
        raw["monitor"]["interval_minutes"] = 15
    elif mutation == "unknown":
        raw["token"] = "secret-not-allowed"
    elif mutation == "retry":
        raw["retry"]["attempts"] = 4
    else:
        raw["providers"] = {"district": False}
    with pytest.raises(ValidationError):
        Config.model_validate(raw)


@pytest.mark.parametrize(
    "field,value",
    [
        ("movie", "Avengers: Endgame"),
        ("city", "Mumbai"),
        ("venue", "Another Cinepolis"),
        ("target_date", "2026-12-19"),
    ],
)
def test_wrong_target_rejected(tmp_path: Path, field: str, value: str) -> None:
    raw = json.loads(FIXTURE.read_text())
    raw[0][field] = value
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_results(path, load_config(CONFIG))


def test_naive_timestamp_and_wrong_local_day_rejected() -> None:
    raw = json.loads(FIXTURE.read_text())[1]
    raw["shows"][0]["starts_at"] = "2026-12-18T10:30:00"
    with pytest.raises(ValidationError):
        ProviderResult.model_validate(raw)
    raw["shows"][0]["starts_at"] = "2026-12-18T23:30:00+00:00"
    with pytest.raises(ValidationError):
        ProviderResult.model_validate(raw)


def test_failure_is_not_availability() -> None:
    raw = json.loads(FIXTURE.read_text())[0]
    raw.update(state="CHECK_FAILED", error="timeout")
    result = ProviderResult.model_validate(raw)
    assert result.earliest_show is None
    raw["shows"] = json.loads(FIXTURE.read_text())[1]["shows"]
    with pytest.raises(ValidationError):
        ProviderResult.model_validate(raw)


def test_redaction() -> None:
    token = "123456:abcdefghijklmnopqrstuvwxyz"
    chat_id = "987654321"
    record = logging.LogRecord(
        "test",
        logging.ERROR,
        "",
        0,
        "https://api.telegram.org/bot%s/sendMessage chat=%s",
        (token, chat_id),
        None,
    )
    output = RedactingFormatter((token, chat_id)).format(record)
    assert token not in output and chat_id not in output
    assert "[REDACTED]" in output
    assert json.loads(output)["timestamp"].endswith("+05:30")


def test_dry_run_no_network_or_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    import socket

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("dry run attempted network access")

    monkeypatch.setattr(socket, "socket", forbidden)
    config, fixture = CONFIG.resolve(), FIXTURE.resolve()
    monkeypatch.chdir(tmp_path)
    assert (
        main(
            ["--config", str(config), "--once", "--dry-run", "--fixture", str(fixture)]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["synthetic"] and output["messages_sent"] == 0
    assert output["production_state_changed"] is False
    assert list(tmp_path.iterdir()) == []


def test_live_mode_fails(capsys: pytest.CaptureFixture) -> None:
    assert main(["--config", str(CONFIG), "--once"]) == 2
    assert "not implemented" in capsys.readouterr().err


def test_validation_does_not_leak_input(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    path = tmp_path / "bad.yml"
    path.write_text("token: do-not-display-this-secret\n")
    assert main(["--config", str(path), "--dry-run", "--fixture", str(FIXTURE)]) == 2
    output = capsys.readouterr().err
    assert "do-not-display-this-secret" not in output
    assert "Validation failed" in output
