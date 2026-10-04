import json
from pathlib import Path

import pytest

from doomsday.cli import main
from doomsday.config import Retry, load_config
from doomsday.delivery import deliver_pending, resolve_event
from doomsday.models import MonitorState, ProviderResult, Show, ShowStatus
from doomsday.state import JsonStore, StateError, apply_results
from doomsday.telegram import TelegramNotifier, format_event
from doomsday.time_utils import IST, now_ist

TOKEN = "123456:fake_test_only"
CHAT = "123"


def notifier(
    responses: list, calls: list, waits: list | None = None
) -> TelegramNotifier:
    def transport(token: str, payload: dict) -> tuple[int, dict]:
        calls.append(payload)
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    return TelegramNotifier(
        TOKEN, CHAT, Retry(), transport, (waits if waits is not None else []).append
    )


SUCCESS = (200, {"ok": True, "result": {"message_id": 42}})


def test_success_payload() -> None:
    calls = []
    assert notifier([SUCCESS], calls).send("Hello").status == "accepted"
    assert calls[0]["allow_paid_broadcast"] is False
    assert "parse_mode" not in calls[0]


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_permanent_rejection(code: int) -> None:
    calls = []
    outcome = notifier([(code, {"ok": False, "error_code": code})], calls).send("Hi")
    assert outcome.status == "failed"
    assert outcome.error == f"TELEGRAM_{code}"
    assert len(calls) == 1


def test_rate_limit_retries_and_long_deferral() -> None:
    calls, waits = [], []
    limited = (429, {"ok": False, "error_code": 429, "parameters": {"retry_after": 2}})
    assert notifier([limited, SUCCESS], calls, waits).send("Hi").status == "accepted"
    assert waits == [2]
    limited[1]["parameters"]["retry_after"] = 120
    outcome = notifier([limited], []).send("Hi")
    assert outcome.status == "pending" and outcome.retry_after == 120


def test_bounded_server_rejections() -> None:
    calls, waits = [], []
    failure = (503, {"ok": False, "error_code": 503})
    assert notifier([failure] * 3, calls, waits).send("Hi").status == "pending"
    assert len(calls) == 3 and waits == [5, 15]


@pytest.mark.parametrize(
    "response", [TimeoutError(TOKEN), (502, {}), (200, {"ok": True}), (200, [])]
)
def test_uncertain_never_retries(response) -> None:
    calls = []
    outcome = notifier([response], calls).send("Hi")
    assert outcome.status == "uncertain" and len(calls) == 1
    assert TOKEN not in str(outcome)


def make_queue(tmp_path: Path):
    config = load_config(Path("config/monitor.yml"))
    from datetime import datetime

    target = config.target
    result = ProviderResult(
        provider="district",
        movie=target.movie,
        city=target.city,
        venue=target.venue,
        target_date=target.date,
        state=MonitorState.FIRST_SHOW_AVAILABLE,
        checked_at=now_ist(),
        shows=[
            Show(
                starts_at=datetime(2026, 12, 18, 9, tzinfo=IST),
                status="AVAILABLE",
                booking_url=config.district.cinema_url,
            )
        ],
    )
    store = JsonStore(tmp_path / "state.json", "production")
    with store.transaction(initialize=True) as state:
        apply_results(state, [result])
    return config, store


def test_durable_claim_and_duplicate_suppression(tmp_path: Path) -> None:
    config, store = make_queue(tmp_path)

    def transport(token: str, payload: dict) -> tuple[int, dict]:
        assert store.read().events[0].status == "sending"
        return SUCCESS

    sender = TelegramNotifier(TOKEN, CHAT, transport=transport)
    assert deliver_pending(store, sender, config)["messages_accepted"] == 1
    assert deliver_pending(store, notifier([], []), config)["messages_accepted"] == 0
    persisted = store.path.read_text()
    assert (
        TOKEN not in persisted
        and "message_id" not in persisted
        and "chat_id" not in persisted
    )
    assert store.read().events[0].status == "accepted"


def test_uncertain_recovery_is_explicit(tmp_path: Path) -> None:
    config, store = make_queue(tmp_path)
    report = deliver_pending(store, notifier([TimeoutError()], []), config)
    assert report["delivery_problems"]
    assert store.read().events[0].status == "uncertain"
    assert deliver_pending(store, notifier([], []), config)["messages_accepted"] == 0
    resolve_event(store, store.read().events[0].id, "retry")
    assert (
        deliver_pending(store, notifier([SUCCESS], []), config)["messages_accepted"]
        == 1
    )


def test_pre_send_write_failure_never_sends(tmp_path: Path, monkeypatch) -> None:
    config, store = make_queue(tmp_path)
    original = store.write

    def fail_claim(state) -> None:
        if state.events[0].status == "sending":
            raise StateError("STATE_WRITE_FAILED")
        original(state)

    monkeypatch.setattr(store, "write", fail_claim)
    calls = []
    with pytest.raises(StateError):
        deliver_pending(store, notifier([SUCCESS], calls), config)
    assert calls == []


def test_post_send_write_failure_holds_claim(tmp_path: Path, monkeypatch) -> None:
    config, store = make_queue(tmp_path)
    original = store.write

    def fail_acceptance(state) -> None:
        if state.events[0].status == "accepted":
            raise StateError("STATE_WRITE_FAILED")
        original(state)

    monkeypatch.setattr(store, "write", fail_acceptance)
    with pytest.raises(StateError):
        deliver_pending(store, notifier([SUCCESS], []), config)
    assert store.read().events[0].status == "sending"
    assert deliver_pending(store, notifier([], []), config)["messages_accepted"] == 0


def test_disabled_and_synthetic_never_send(tmp_path: Path) -> None:
    config, store = make_queue(tmp_path)
    config.notifications.enabled = False
    assert deliver_pending(store, notifier([], []), config)["delivery_disabled"]
    config.notifications.enabled = True
    synthetic = JsonStore(tmp_path / "synthetic.json", "synthetic")
    with synthetic.transaction(initialize=True):
        pass
    with pytest.raises(StateError, match="SYNTHETIC"):
        deliver_pending(synthetic, notifier([], []), config)


def test_legacy_migration_and_health_throttling(tmp_path: Path) -> None:
    from datetime import timedelta

    config, store = make_queue(tmp_path)
    raw = json.loads(store.path.read_text())
    raw["version"] = 1
    for event in raw["events"]:
        for field in ["attempts", "last_error", "next_attempt_at", "report_results"]:
            del event[field]
    store.path.write_text(json.dumps(raw))
    assert store.read().version == 3
    with store.transaction() as state:
        base = state.events[0].observation
        for n in range(1, 6):
            failure = base.model_copy(
                update={
                    "checked_at": base.checked_at + timedelta(minutes=n),
                    "shows": [],
                    "error": "HTTP_403",
                    "state": MonitorState.CHECK_FAILED,
                }
            )
            apply_results(state, [failure])
        assert len(state.events) == 2
        text = format_event(state.events[-1])
        assert "Three consecutive" in text and "IST" in text
        assert "Earliest bookable" not in text


def test_cli_rejects_fixture_delivery(tmp_path: Path) -> None:
    assert (
        main(
            [
                "--fixture",
                "tests/fixtures/preview.json",
                "--state",
                str(tmp_path / "x"),
                "--notify",
            ]
        )
        == 2
    )


def test_rate_limit_survives_restart(tmp_path: Path) -> None:
    config, store = make_queue(tmp_path)
    limited = (
        429,
        {"ok": False, "error_code": 429, "parameters": {"retry_after": 120}},
    )
    report = deliver_pending(store, notifier([limited], []), config)
    assert report["delivery_problems"][0]["error"] == "RATE_LIMITED"
    assert store.read().events[0].next_attempt_at is not None
    calls = []
    report = deliver_pending(store, notifier([], calls), config)
    assert calls == [] and report["delivery_problems"][0]["error"] == "RETRY_DEFERRED"


def test_superseded_event_not_sent(tmp_path: Path) -> None:
    from datetime import timedelta

    config, store = make_queue(tmp_path)
    with store.transaction() as state:
        initial = state.events[0].observation
        result = initial.model_copy(
            update={
                "checked_at": initial.checked_at + timedelta(seconds=1),
                "shows": [],
                "state": MonitorState.MOVIE_LISTED,
            }
        )
        apply_results(state, [result])
    assert deliver_pending(store, notifier([], []), config)["messages_accepted"] == 0
    assert store.read().events[0].status == "skipped"


def test_message_content_and_status_change(tmp_path: Path) -> None:
    from datetime import timedelta

    config, store = make_queue(tmp_path)
    with store.transaction() as state:
        event = state.events[0]
        text = format_event(event)
        assert "09:00 AM" in text and "IST" in text
        assert str(event.show.booking_url) in text
        assert config.target.movie in text and config.target.venue in text
        changed = event.observation.model_copy(deep=True)
        changed.checked_at += timedelta(seconds=1)
        changed.shows[0].status = ShowStatus.FAST_FILLING
        apply_results(state, [ProviderResult.model_validate(changed.model_dump())])
    assert (
        deliver_pending(store, notifier([SUCCESS], []), config)["messages_accepted"]
        == 1
    )


def test_accepted_resolution_no_resend(tmp_path: Path) -> None:
    config, store = make_queue(tmp_path)
    with store.transaction() as state:
        state.events[0].status = "sending"
    resolve_event(store, store.read().events[0].id, "accepted")
    assert deliver_pending(store, notifier([], []), config)["messages_accepted"] == 0


def test_cli_test_is_explicit_and_mocked(monkeypatch, capsys) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", CHAT)
    calls = []
    monkeypatch.setattr(
        TelegramNotifier, "from_environment", lambda retry: notifier([SUCCESS], calls)
    )
    assert main(["--telegram-test"]) == 0
    assert calls[0]["text"].startswith("TEST")
    assert "not a ticket availability alert" in calls[0]["text"]
    assert TOKEN not in capsys.readouterr().out
