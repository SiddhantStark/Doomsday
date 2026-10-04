from datetime import datetime
from pathlib import Path

from doomsday.config import load_config
from doomsday.delivery import deliver_pending
from doomsday.models import EventKind, MonitorState, Provider, ProviderResult
from doomsday.state import JsonStore, apply_results
from doomsday.telegram import TelegramNotifier, format_event
from doomsday.time_utils import IST


def test_combined_summary_persistence_and_deduplication(tmp_path):
    config = load_config(Path("config/monitor.yml"))
    target = config.target
    results = [
        ProviderResult(
            provider=p,
            movie=target.movie,
            city=target.city,
            venue=target.venue,
            target_date=target.date,
            checked_at=datetime(2026, 10, 4, 20, tzinfo=IST),
            state=MonitorState.COMING_SOON
            if p == Provider.BOOKMYSHOW
            else MonitorState.CHECK_FAILED,
            error=None if p == Provider.BOOKMYSHOW else "HTTP_403",
        )
        for p in Provider
    ]
    store = JsonStore(tmp_path / "state.json", "production")
    with store.transaction(initialize=True) as state:
        events = apply_results(state, results, summary=True)
        assert len(events) == 1
        assert events[0].kind == EventKind.STATUS_SUMMARY
        text = format_event(events[0])
        assert "bookings not open" in text
        assert "Check failed — availability unknown" in text
        assert "04 Oct 2026" in text
    sent = []

    def transport(token, payload):
        sent.append(payload["text"])
        return 200, {"ok": True, "result": {"message_id": 1}}

    notifier = TelegramNotifier("123:fake", "123", transport=transport)
    assert deliver_pending(store, notifier, config)["messages_accepted"] == 1
    with store.transaction() as state:
        assert apply_results(state, results, summary=True) == []
    assert deliver_pending(store, notifier, config)["messages_accepted"] == 0
    assert len(sent) == 1


def test_existing_v2_state_migrates_without_losing_history(tmp_path):
    import json

    store = JsonStore(tmp_path / "state.json", "production")
    store.path.write_text(
        json.dumps(
            {"version": 2, "namespace": "production", "observations": {}, "events": []}
        )
    )
    assert store.read().version == 3
    assert json.loads(store.path.read_text())["version"] == 2
