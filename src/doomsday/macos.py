"""LaunchAgent entry point with a whole-run lock and bounded local logs."""

import fcntl
import json
import logging
import os
from contextlib import redirect_stderr, redirect_stdout
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .scheduled import main as scheduled_main
from .time_utils import now_ist


class LogStream:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def write(self, text: str) -> int:
        for line in text.splitlines():
            if line.strip():
                self.logger.info(line)
        return len(text)

    def flush(self) -> None:
        pass


def main() -> int:
    root = Path.cwd()
    runtime = root / ".monitor"
    runtime.mkdir(exist_ok=True)
    os.chmod(runtime, 0o700)
    with (runtime / "run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        logger = logging.getLogger("doomsday.launchagent")
        logger.propagate = False
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(
            runtime / "monitor.log", maxBytes=1_000_000, backupCount=3
        )
        logger.addHandler(handler)
        code = 3
        try:
            with redirect_stdout(LogStream(logger)), redirect_stderr(LogStream(logger)):
                code = scheduled_main(
                    ["--state", str(runtime / "state.json"), "--headed", "--notify"]
                )
        except Exception:
            logger.error("LAUNCHAGENT_RUN_FAILED")
        finally:
            status = {"finished_at": now_ist().isoformat(), "exit_code": code}
            temporary = runtime / "last-run.tmp"
            temporary.write_text(json.dumps(status, indent=2) + "\n")
            temporary.replace(runtime / "last-run.json")
            logger.removeHandler(handler)
            handler.close()
        return code


if __name__ == "__main__":
    raise SystemExit(main())
