from pathlib import Path

import pytest
from test_district import setup_schedule, snapshot

from doomsday import scheduled
from doomsday.bookmyshow import CheckError
from doomsday.config import load_locations
from doomsday.district import parse_schedule
from doomsday.models import MonitorState, ProviderResult
from doomsday.state import JsonStore, apply_results
from doomsday.time_utils import now_ist


def test_location_checks_continue_after_provider_failure(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    with JsonStore(path, "production").transaction(initialize=True):
        pass
    calls = []

    def run(args):
        calls.append(args)
        return 1 if len(calls) == 1 else 0

    monkeypatch.setattr(scheduled, "monitor_main", run)
    assert (
        scheduled.main(
            ["--state", str(path), "--locations", "config/locations.yml", "--headed"]
        )
        == 1
    )
    assert len(calls) == 2
    assert "config/monitor-mumbai.yml" in calls[1]


def test_target_state_and_cadence_are_independent(tmp_path):
    configs = load_locations(Path("config/locations.yml"))
    assert len(configs) == 2
    store = JsonStore(tmp_path / "state.json", "production")
    now = now_ist()
    with store.transaction(initialize=True) as state:
        for _, c in configs:
            results = [
                ProviderResult(
                    provider=p,
                    movie=c.target.movie,
                    city=c.target.city,
                    venue=c.target.venue,
                    target_date=c.target.date,
                    checked_at=now,
                    state=MonitorState.MOVIE_LISTED,
                )
                for p in c.providers
            ]
            events = apply_results(state, results, summary=True)
            assert len(events) == 1
        assert len(state.observations) == 4
        assert len({e.target_key for e in state.events}) == 2
        assert all(scheduled.due(c, state, now) == "not_due" for _, c in configs)
    assert len(store.read().events) == 2


def test_blank_city_requires_explicit_address_match():
    target, settings, data = setup_schedule()
    page = data["props"]["pageProps"]["data"]
    page["cityLabel"] = ""
    cinema = next(iter(page["serverState"].values()))["meta"]["cinema"]
    cinema["address"] = "Road, Chennai, Tamil Nadu, India"
    assert parse_schedule(
        snapshot(settings, target, data), target, settings
    ).earliest_show
    cinema["address"] = "Road, NotChennai, India"
    with pytest.raises(CheckError, match="CITY"):
        parse_schedule(snapshot(settings, target, data), target, settings)


def test_delivery_does_not_mix_venues(tmp_path, monkeypatch):
    from doomsday.delivery import deliver_pending
    from doomsday.telegram import TelegramNotifier

    configs = load_locations(Path("config/locations.yml"))
    store = JsonStore(tmp_path / "state.json", "production")
    with store.transaction(initialize=True) as state:
        for _, c in configs:
            result = ProviderResult(
                provider="district",
                movie=c.target.movie,
                city=c.target.city,
                venue=c.target.venue,
                target_date=c.target.date,
                checked_at=now_ist(),
                state=MonitorState.MOVIE_LISTED,
            )
            apply_results(state, [result], summary=True)
    sent = []

    def transport(token, payload):
        sent.append(payload["text"])
        return 200, {"ok": True, "result": {"message_id": 1}}

    notifier = TelegramNotifier("123:fake", "123", transport=transport)
    assert deliver_pending(store, notifier, configs[0][1])["messages_accepted"] == 1
    assert "Chennai" in sent[0] and "Mumbai" not in sent[0]
    assert deliver_pending(store, notifier, configs[1][1])["messages_accepted"] == 1
    assert "Mumbai" in sent[1] and "Chennai" not in sent[1]


def test_invalid_location_manifest_rejected(tmp_path):
    path = tmp_path / "locations.yml"
    path.write_text("locations: []\n")
    with pytest.raises(ValueError):
        load_locations(path)
