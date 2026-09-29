"""Fast-forward state-branch persistence for a dedicated, preconfigured checkout."""

import fcntl
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .state import JsonStore, State, StateError


class GitStore:
    def __init__(self, checkout: Path) -> None:
        self.checkout = checkout.resolve()
        self.local = JsonStore(self.checkout / "state.json", "production")

    def git(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.checkout), *args],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            # Remote URLs and credentials must never reach logs.
            raise StateError("STATE_GIT_OPERATION_FAILED") from None

    @contextmanager
    def transaction(
        self, initialize: bool = False, readonly: bool = False
    ) -> Iterator[State]:
        if readonly:
            raise StateError("USE_LOCAL_STATE_FOR_GIT_DRY_RUN")
        if Path(self.git("rev-parse", "--show-toplevel")).resolve() != self.checkout:
            raise StateError("STATE_REQUIRES_DEDICATED_CHECKOUT")
        if self.git("branch", "--show-current") != "monitor-state":
            raise StateError("STATE_BRANCH_MISMATCH")
        lock_path = Path(self.git("rev-parse", "--absolute-git-dir")) / "monitor.lock"
        with lock_path.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise StateError("STATE_LOCKED") from None
            try:
                with self.synchronized_transaction(initialize) as state:
                    yield state
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    @contextmanager
    def synchronized_transaction(self, initialize: bool) -> Iterator[State]:
        if self.git("status", "--porcelain", "--untracked-files=no"):
            raise StateError("STATE_CHECKOUT_DIRTY")
        # Require the remote branch to exist, and reject unpushed local commits.
        self.git("fetch", "origin", "monitor-state")
        self.git("merge", "--ff-only", "FETCH_HEAD")
        if self.git("rev-parse", "HEAD") != self.git("rev-parse", "FETCH_HEAD"):
            raise StateError("STATE_BRANCH_DIVERGED")
        with self.local.transaction(initialize=initialize) as state:
            yield state
        self.git("add", "--", "state.json")
        if self.git("diff", "--cached", "--name-only"):
            self.git("commit", "-m", "Update monitor observations and outbox")
            self.git("push", "origin", "HEAD:refs/heads/monitor-state")
        # A failed push leaves local evidence for recovery and raises; no sender
        # may proceed until this context has exited successfully.
