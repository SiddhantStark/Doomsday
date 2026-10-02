"""Phase 7 acceptance scenarios: isolated state and a fake Telegram transport."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from doomsday import scheduled
from doomsday.config import load_config
from doomsday.delivery import deliver_pending
from doomsday.models import MonitorState, Provider, ProviderResult, Show, ShowStatus
from doomsday.state import JsonStore, apply_results
from doomsday.telegram import TelegramNotifier
from doomsday.time_utils import IST


def test_detection_delivery_restart_sequence(tmp_path, monkeypatch):
    config = load_config(Path("config/monitor.yml"))
    clock = datetime(2026, 12, 1, 12, tzinfo=IST)
    monkeypatch.setattr("doomsday.delivery.now_ist", lambda: clock)
    calls = []
    path = tmp_path / "isolated-state.json"

    def transport(token, payload):
        persisted = JsonStore(path, "production").read()
        assert any(e.status == "sending" for e in persisted.events)
        calls.append(payload["text"])
        return 200, {"ok": True, "result": {"message_id": len(calls)}}

    notifier = TelegramNotifier("123:test", "123", transport=transport)
    sequence = [
        (None, False),
        (10, False),
        (10, False),
        (8, False),
        (None, True),
        (8, False),
        (None, False),
        (8, False),
    ]
    for step, (hour, failed) in enumerate(sequence):
        target = config.target
        result = ProviderResult(
            provider=Provider.DISTRICT,
            movie=target.movie,
            city=target.city,
            venue=target.venue,
            target_date=target.date,
            checked_at=clock + timedelta(minutes=step),
            state=MonitorState.CHECK_FAILED
            if failed
            else (
                MonitorState.FIRST_SHOW_AVAILABLE if hour else MonitorState.MOVIE_LISTED
            ),
            shows=[
                Show(
                    starts_at=datetime(2026, 12, 18, hour, tzinfo=IST),
                    status=ShowStatus.AVAILABLE,
                    booking_url=config.district.cinema_url,
                )
            ]
            if hour
            else [],
            error="HTTP_403" if failed else None,
        )
        store = JsonStore(path, "production")
        with store.transaction(initialize=step == 0) as state:
            apply_results(state, [result])
        deliver_pending(store, notifier, config)
        # New store instance models restart; accepted events must never resend.
        assert (
            deliver_pending(JsonStore(path, "production"), notifier, config)[
                "messages_accepted"
            ]
            == 0
        )
    assert len(calls) == 3
    assert [text.splitlines()[0] for text in calls] == [
        "Tickets available",
        "Earlier show available",
        "Tickets available again",
    ]
    assert all(
        e.status == "accepted" for e in JsonStore(path, "production").read().events
    )


@pytest.mark.parametrize(
    "field,value",
    [("movie", "Other movie"), ("city", "Mumbai"), ("venue", "Other cinema")],
)
def test_wrong_target_queue_never_sends(tmp_path, field, value):
    from test_telegram import make_queue, notifier

    config, store = make_queue(tmp_path)
    setattr(config.target, field, value)
    assert deliver_pending(store, notifier([], []), config)["messages_accepted"] == 0
    assert store.read().events[0].status == "pending"


def test_end_date_stops_even_forced_notifications(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    with JsonStore(path, "production").transaction(initialize=True):
        pass
    before = path.read_bytes()
    # 18:30 UTC on December 18 is midnight December 19 in Chennai.
    from datetime import timezone

    monkeypatch.setattr(
        scheduled,
        "now_ist",
        lambda: datetime(2026, 12, 18, 18, 30, tzinfo=timezone.utc),
    )

    def forbidden(args):
        pytest.fail("Expired target must not check providers or send notifications")

    monkeypatch.setattr(scheduled, "monitor_main", forbidden)
    assert (
        scheduled.main(["--state", str(path), "--force", "--notify", "--headed"]) == 0
    )
    assert path.read_bytes() == before


def test_health_missing_provider_cannot_be_healthy(tmp_path, monkeypatch, capsys):
    import json

    from doomsday.health import main

    path = tmp_path / "state.json"
    with JsonStore(path, "production").transaction(initialize=True):
        pass
    monkeypatch.setattr("sys.argv", ["health", "--state", str(path)])
    assert main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["healthy"] is False
    assert len(report["observations"]) == 2
    assert all(o["missing"] for o in report["observations"])
