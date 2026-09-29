from datetime import datetime, timedelta
from pathlib import Path

import pytest

from doomsday.cli import main
from doomsday.models import EventKind, MonitorState, Provider, ProviderResult, Show
from doomsday.state import JsonStore, StateError, apply_results, mark_accepted
from doomsday.time_utils import IST


def observation(
    step: int, hour: int | None = None, failed: bool = False
) -> ProviderResult:
    return ProviderResult(
        provider="district",
        movie="Test",
        city="Chennai",
        venue="BSR",
        target_date="2026-12-18",
        checked_at=datetime(2026, 12, 1, tzinfo=IST) + timedelta(minutes=step),
        state=MonitorState.CHECK_FAILED
        if failed
        else (MonitorState.FIRST_SHOW_AVAILABLE if hour else MonitorState.MOVIE_LISTED),
        shows=[
            Show(starts_at=datetime(2026, 12, 18, hour, tzinfo=IST), status="AVAILABLE")
        ]
        if hour
        else [],
        error="HTTP_403" if failed else None,
    )


def test_acceptance_sequence_across_restarts(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    kinds = []
    for step, (hour, failed) in enumerate(
        [
            (None, False),
            (10, False),
            (10, False),
            (8, False),
            (None, True),
            (8, False),
            (None, False),
            (8, False),
        ]
    ):
        with JsonStore(path, "production").transaction(initialize=step == 0) as state:
            kinds.extend(
                e.kind for e in apply_results(state, [observation(step, hour, failed)])
            )
    assert kinds == [
        EventKind.BOOKING_OPENED,
        EventKind.EARLIER_SHOW_ADDED,
        EventKind.AVAILABILITY_REAPPEARED,
    ]
    state = JsonStore(path, "production").read()
    assert len(state.events) == 3
    assert all(e.status == "pending" for e in state.events)
    with JsonStore(path, "production").transaction() as state:
        mark_accepted(state, state.events[0].id)
    assert JsonStore(path, "production").read().events[0].status == "accepted"


def test_missing_corrupt_and_initialization(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "state.json", "production")
    with pytest.raises(StateError, match="MISSING"):
        with store.transaction():
            pass
    with store.transaction(initialize=True):
        pass
    with pytest.raises(StateError, match="ALREADY_EXISTS"):
        with store.transaction(initialize=True):
            pass
    for text in ["{", "{}", '{"namespace":"production"}']:
        store.path.write_text(text)
        with pytest.raises(StateError, match="CORRUPT"):
            store.read()


def test_overlap_and_rollback(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "state.json", "production")
    with store.transaction(initialize=True):
        with pytest.raises(StateError, match="LOCKED"):
            with store.transaction(initialize=True):
                pass
    before = store.path.read_bytes()
    with pytest.raises(RuntimeError):
        with store.transaction() as state:
            apply_results(state, [observation(1, 10)])
            raise RuntimeError("crash before commit")
    assert store.path.read_bytes() == before


def test_atomic_write_failure_preserves_original(tmp_path: Path, monkeypatch) -> None:
    store = JsonStore(tmp_path / "state.json", "production")
    with store.transaction(initialize=True):
        pass
    before = store.path.read_bytes()

    def fail(*args):
        raise OSError("disk error")

    monkeypatch.setattr("doomsday.state.os.replace", fail)
    with pytest.raises(StateError, match="WRITE_FAILED"):
        with store.transaction() as state:
            apply_results(state, [observation(1, 10)])
    assert store.path.read_bytes() == before


def test_stale_unknown_and_failed_checks(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "state.json", "production")
    with store.transaction(initialize=True) as state:
        apply_results(state, [observation(2, 10)])
        assert not apply_results(state, [observation(1)])
        unknown = observation(3).model_copy(
            update={
                "shows": [
                    Show(
                        starts_at=datetime(2026, 12, 18, 10, tzinfo=IST),
                        status="UNKNOWN",
                    )
                ]
            }
        )
        assert not apply_results(state, [unknown])
        assert not apply_results(state, [observation(4, failed=True)])
        assert not apply_results(state, [observation(5, 10)])
        assert len(state.events) == 1


def test_independent_targets_and_namespaces(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "state.json", "synthetic")
    with store.transaction(initialize=True) as state:
        first = observation(1, 10)
        second = first.model_copy(update={"provider": Provider.BOOKMYSHOW})
        assert len(apply_results(state, [first, second])) == 2
    with pytest.raises(StateError, match="NAMESPACE"):
        JsonStore(store.path, "production").read()


def test_dry_run_and_cli_restart(tmp_path: Path, capsys) -> None:
    path = tmp_path / "test.json"
    args = ["--fixture", "tests/fixtures/preview.json", "--state", str(path)]
    assert main([*args, "--init-state"]) == 0
    capsys.readouterr()
    before = path.read_bytes()
    assert main([*args, "--dry-run"]) == 0
    assert path.read_bytes() == before
    capsys.readouterr()
    assert main(args) == 0
    import json

    assert json.loads(capsys.readouterr().out)["new_events"] == []
    path.unlink()
    assert main(args) == 3
