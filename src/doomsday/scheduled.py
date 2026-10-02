"""Cloud entry point: date/cadence gate and one durable monitor run."""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from .cli import main as monitor_main
from .config import Config, load_config
from .state import JsonStore, State, StateError
from .time_utils import IST, now_ist


def due(config: Config, state: State, now: datetime, force: bool = False) -> str:
    day = now.astimezone(IST).date()
    if day > config.target.date:
        return "target_date_ended"
    if force:
        return "due"
    checks = []
    for provider, enabled in config.providers.items():
        if not enabled:
            continue
        from .models import MonitorState, ProviderResult
        from .state import target_key

        key = target_key(
            ProviderResult(
                provider=provider,
                movie=config.target.movie,
                city=config.target.city,
                venue=config.target.venue,
                target_date=config.target.date,
                state=MonitorState.MOVIE_LISTED,
                checked_at=now,
            )
        )
        item = state.observations.get(key)
        if item is None:
            return "due"
        checks.append(item.last_check)
    if not checks:
        return "no_enabled_providers"
    # Small tolerance avoids a whole-hour skip due to runner startup jitter.
    interval = timedelta(minutes=config.monitor.interval_on(day) - 5)
    return "due" if now - min(checks) >= interval else "not_due"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    backend = parser.add_mutually_exclusive_group(required=True)
    backend.add_argument("--state-repo", type=Path)
    backend.add_argument("--state", type=Path)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--config", type=Path, default=Path("config/monitor.yml"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--gate-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        state_path = args.state or args.state_repo / "state.json"
        state = JsonStore(state_path, "production").read()
        decision = due(config, state, now_ist(), args.force)
        if args.gate_only:
            print("true" if decision == "due" else "false")
            return 0
        print(
            json.dumps(
                {
                    "schedule_decision": decision,
                    "interval_minutes": config.monitor.interval_on(now_ist().date()),
                }
            )
        )
        if decision != "due":
            return 0
        command = [
            "--config",
            str(args.config),
            "--provider",
            "all",
            "--state" if args.state else "--state-repo",
            str(args.state or args.state_repo),
        ]
        if args.headed:
            command.append("--headed")
        if args.notify:
            command.append("--notify")
        return monitor_main(command)
    except (StateError, ValueError, OSError):
        print(json.dumps({"error": "SCHEDULE_STATE_OR_CONFIG_INVALID"}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
