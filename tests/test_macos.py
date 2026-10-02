import json
from pathlib import Path

from doomsday import macos
from doomsday.scheduled import main
from doomsday.state import JsonStore


def test_agent_records_outcome_without_exposing_exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def fail(args):
        raise RuntimeError("private transport details")

    monkeypatch.setattr(macos, "scheduled_main", fail)
    assert macos.main() == 3
    assert (
        json.loads((tmp_path / ".monitor/last-run.json").read_text())["exit_code"] == 3
    )
    assert (
        "private transport details"
        not in (tmp_path / ".monitor/monitor.log").read_text()
    )


def test_local_scheduler_forwards_headed_and_notify(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    with JsonStore(path, "production").transaction(initialize=True):
        pass
    calls = []
    monkeypatch.setattr(
        "doomsday.scheduled.monitor_main", lambda args: calls.append(args) or 0
    )
    assert main(["--state", str(path), "--headed", "--notify"]) == 0
    assert "--headed" in calls[0] and "--notify" in calls[0]
    assert "--state-repo" not in calls[0]
    assert str(Path(path)) in calls[0]
