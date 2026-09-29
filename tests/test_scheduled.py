from datetime import datetime, timedelta
from pathlib import Path

from doomsday.config import load_config
from doomsday.models import MonitorState, ProviderResult
from doomsday.scheduled import due
from doomsday.state import State, apply_results
from doomsday.time_utils import IST


def test_cadence_and_end_date() -> None:
    config = load_config(Path("config/monitor.yml"))
    state = State(namespace="production")
    for month, hours in [(9, 24), (11, 6), (12, 1)]:
        now = datetime(2026, month, 1, 12, tzinfo=IST)
        assert due(config, State(namespace="production"), now) == "due"
        results = [
            ProviderResult(
                provider=p,
                movie=config.target.movie,
                city=config.target.city,
                venue=config.target.venue,
                target_date=config.target.date,
                state=MonitorState.CHECK_FAILED,
                checked_at=now,
                error="HTTP_403",
            )
            for p in config.providers
        ]
        apply_results(state, results)
        assert due(config, state, now + timedelta(minutes=10)) == "not_due"
        assert due(config, state, now + timedelta(hours=hours)) == "due"
        assert due(config, state, now, force=True) == "due"
    assert (
        due(config, state, datetime(2026, 12, 19, tzinfo=IST), force=True)
        == "target_date_ended"
    )
