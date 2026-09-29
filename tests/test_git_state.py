import subprocess
from pathlib import Path

import pytest
from test_state import observation

from doomsday.git_state import GitStore
from doomsday.state import StateError, apply_results


def git(path: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), *args], text=True, stderr=subprocess.DEVNULL
    ).strip()


def checkout(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    git(remote, "init", "--bare")
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-b", "monitor-state")
    git(work, "config", "user.name", "Test")
    git(work, "config", "user.email", "test@example.invalid")
    git(work, "commit", "--allow-empty", "-m", "Initialize state branch")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "-u", "origin", "monitor-state")
    return work


def test_fresh_checkout_recovers_events(tmp_path: Path) -> None:
    work = checkout(tmp_path)
    with GitStore(work).transaction(initialize=True) as state:
        apply_results(state, [observation(1, 10)])
    restored = tmp_path / "restored"
    git(
        tmp_path,
        "clone",
        "--branch",
        "monitor-state",
        str(tmp_path / "remote.git"),
        str(restored),
    )
    with GitStore(restored).transaction() as state:
        assert len(state.events) == 1
        assert not apply_results(state, [observation(1, 10)])
    assert git(work, "rev-parse", "HEAD") == git(restored, "rev-parse", "HEAD")


def test_push_failure_blocks_completion(tmp_path: Path, monkeypatch) -> None:
    work = checkout(tmp_path)
    store = GitStore(work)
    original = store.git

    def failing_git(*args: str) -> str:
        if args[0] == "push":
            raise StateError("STATE_GIT_OPERATION_FAILED")
        return original(*args)

    monkeypatch.setattr(store, "git", failing_git)
    with pytest.raises(StateError, match="GIT_OPERATION_FAILED"):
        with store.transaction(initialize=True) as state:
            apply_results(state, [observation(1, 10)])
    assert store.local.read().events[0].status == "pending"
    with pytest.raises(StateError, match="DIVERGED"):
        with GitStore(work).transaction():
            pass


def test_wrong_branch_and_nested_repo(tmp_path: Path) -> None:
    work = checkout(tmp_path)
    nested = work / "nested"
    nested.mkdir()
    with pytest.raises(StateError, match="DEDICATED"):
        with GitStore(nested).transaction():
            pass
    git(work, "checkout", "-b", "main")
    with pytest.raises(StateError, match="BRANCH_MISMATCH"):
        with GitStore(work).transaction():
            pass
