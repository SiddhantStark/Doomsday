"""Read-only local readiness report; no messages, browser calls, or writes."""

import argparse
import json
from pathlib import Path

from .config import load_config
from .models import MonitorState, ProviderResult
from .state import JsonStore, target_key
from .time_utils import now_ist


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, default=Path(".monitor/state.json"))
    parser.add_argument("--config", type=Path, default=Path("config/monitor.yml"))
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        state = JsonStore(args.state, "production").read()
        now = now_ist()
        ended = now.date() > config.target.date
        interval = config.monitor.interval_on(now.date())
        observations = []
        for provider, enabled in config.providers.items():
            if not enabled:
                continue
            identity = ProviderResult(
                provider=provider,
                movie=config.target.movie,
                city=config.target.city,
                venue=config.target.venue,
                target_date=config.target.date,
                state=MonitorState.MOVIE_LISTED,
                checked_at=now,
            )
            item = state.observations.get(target_key(identity))
            if item is None:
                observations.append(
                    {
                        "provider": provider.value,
                        "missing": True,
                        "stale": True,
                        "consecutive_failures": 0,
                    }
                )
                continue
            result = item.last_success
            observations.append(
                {
                    "provider": result.provider.value
                    if result
                    else "unknown_until_success",
                    "last_check": item.last_check.isoformat(),
                    "last_success": result.checked_at.isoformat() if result else None,
                    "state": result.state.value if result else None,
                    "consecutive_failures": item.failures,
                    "stale": not ended
                    and (now - item.last_check).total_seconds() > (interval + 120) * 60,
                }
            )
        unresolved = [
            {"id": e.id, "status": e.status, "error": e.last_error}
            for e in state.events
            if e.status not in ("accepted", "skipped")
        ]
        healthy = (
            bool(observations)
            and not unresolved
            and all(
                not o["stale"] and o["consecutive_failures"] == 0 for o in observations
            )
        )
        print(
            json.dumps(
                {
                    "reviewed_at": now.isoformat(),
                    "target_date_ended": ended,
                    "interval_minutes": interval,
                    "healthy": healthy,
                    "observations": observations,
                    "unresolved_events": unresolved,
                },
                indent=2,
            )
        )
        return 0 if healthy else 1
    except (ValueError, OSError):
        print(json.dumps({"healthy": False, "error": "STATE_OR_CONFIG_UNREADABLE"}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
