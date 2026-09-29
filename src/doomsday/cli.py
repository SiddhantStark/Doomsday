"""One-run checks, persistent observations, and notification previews."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .git_state import GitStore

from dotenv import load_dotenv
from pydantic import ValidationError
from yaml import YAMLError

from .config import Config, load_config
from .logging_utils import configure_logging
from .models import EventKind, NotificationEvent, ProviderResult
from .state import JsonStore, StateError, apply_results
from .time_utils import IST, now_ist

logger = logging.getLogger(__name__)


def normalize(value: str) -> str:
    return " ".join(
        "".join(c if c.isalnum() else " " for c in value.casefold()).split()
    )


def load_results(path: Path, config: Config) -> list[ProviderResult]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, list):
        raise ValueError("fixture must be a list of provider results")
    results = [ProviderResult.model_validate(item) for item in raw]
    seen = set()
    for result in results:
        if result.provider in seen:
            raise ValueError("duplicate provider in fixture")
        seen.add(result.provider)
        target = config.target
        aliases = {normalize(v) for v in [target.venue, *target.venue_aliases]}
        if (
            normalize(result.movie) != normalize(target.movie)
            or normalize(result.city) != normalize(target.city)
            or normalize(result.venue) not in aliases
            or result.target_date != target.date
        ):
            raise ValueError("fixture target does not match configuration")
    enabled = {provider for provider, active in config.providers.items() if active}
    if not enabled.issubset(seen):
        raise ValueError("fixture missing an enabled provider")
    return [result for result in results if result.provider in enabled]


def preview(results: list[ProviderResult], config: Config) -> dict:
    events = []
    for result in results:
        show = result.earliest_show
        if show and config.notifications.enabled:
            events.append(
                NotificationEvent(
                    kind=EventKind.BOOKING_OPENED,
                    provider=result.provider,
                    target_date=result.target_date,
                    created_at=now_ist(),
                    first_show=show.starts_at.astimezone(IST).time(),
                    booking_url=show.booking_url,
                ).model_dump(mode="json")
            )
    return {
        "mode": "fixture_preview",
        "synthetic": True,
        "assumption": "No previous state; illustrative first-availability events only",
        "interval_minutes": config.monitor.interval_on(now_ist().date()),
        "results": [result.model_dump(mode="json") for result in results],
        "intended_events": events,
        "messages_sent": 0,
        "production_state_changed": False,
    }


def persist_results(results: list[ProviderResult], args: argparse.Namespace) -> dict:
    from .git_state import GitStore

    namespace = "synthetic" if args.fixture else "production"
    store = (
        GitStore(args.state_repo)
        if args.state_repo
        else JsonStore(args.state, namespace)
    )
    with store.transaction(initialize=args.init_state, readonly=args.dry_run) as state:
        events = apply_results(state, results)
        pending = [
            e.model_dump(mode="json") for e in state.events if e.status == "pending"
        ]
    return {
        "mode": "state_preview" if args.dry_run else "state_recorded",
        "new_events": [e.model_dump(mode="json") for e in events],
        "pending_events": pending,
        "production_state_changed": not args.dry_run and namespace == "production",
        "state_written": not args.dry_run,
    }


def production_store(args: argparse.Namespace) -> JsonStore | "GitStore":
    from .git_state import GitStore

    return (
        GitStore(args.state_repo)
        if args.state_repo
        else JsonStore(args.state, "production")
    )


def send_queue(args: argparse.Namespace, config: Config) -> dict:
    from .delivery import deliver_pending
    from .telegram import TelegramNotifier

    if not config.notifications.enabled:
        return {
            "messages_accepted": 0,
            "delivery_problems": [],
            "delivery_disabled": True,
        }
    return deliver_pending(
        production_store(args), TelegramNotifier.from_environment(config.retry), config
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/monitor.yml"))
    parser.add_argument("--once", action="store_true", help="Run once (the default)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without side effects"
    )
    parser.add_argument(
        "--fixture", type=Path, help="Synthetic normalized results JSON"
    )
    parser.add_argument(
        "--provider",
        choices=["bookmyshow", "district", "all"],
        help="Live read-only check",
    )
    parser.add_argument("--state", type=Path, help="Local durable JSON state")
    parser.add_argument(
        "--state-repo", type=Path, help="Dedicated monitor-state checkout"
    )
    parser.add_argument(
        "--init-state", action="store_true", help="Explicitly initialize new state"
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Deliver queued production events after recording checks",
    )
    parser.add_argument(
        "--send-pending",
        action="store_true",
        help="Deliver existing production queue without checking providers",
    )
    parser.add_argument(
        "--telegram-test",
        action="store_true",
        help="Send one clearly labeled test message",
    )
    parser.add_argument("--resolve-event", help="Resolve an uncertain/failed event ID")
    parser.add_argument("--resolution", choices=["retry", "accepted"])
    args = parser.parse_args(argv)
    load_dotenv()
    secrets = tuple(
        os.getenv(key, "") for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
    )
    configure_logging("INFO", secrets)
    try:
        config = load_config(args.config)
        configure_logging(config.log_level, secrets)
        if args.state and args.state_repo:
            raise ValueError("select one state backend")
        if args.init_state and (args.dry_run or not (args.state or args.state_repo)):
            raise ValueError("initialization requires writable state")
        if args.state_repo and (args.fixture or args.dry_run):
            raise ValueError("Git state requires a live non-dry run")
        delivery_action = args.notify or args.send_pending or args.resolve_event
        if args.resolution and not args.resolve_event:
            raise ValueError("resolution requires an event ID")
        if delivery_action and (
            args.dry_run or args.fixture or not (args.state or args.state_repo)
        ):
            raise ValueError("delivery requires writable production state")
        if args.notify and not args.provider:
            raise ValueError("notify requires provider checks")
        if (
            sum(
                bool(v)
                for v in (
                    args.notify,
                    args.send_pending,
                    args.resolve_event,
                    args.telegram_test,
                )
            )
            > 1
        ):
            raise ValueError("choose one delivery action")
        if (args.send_pending or args.resolve_event) and (
            args.provider or args.init_state
        ):
            raise ValueError("queue operations cannot initialize or check providers")
        if args.telegram_test:
            if (
                args.provider
                or args.fixture
                or args.state
                or args.state_repo
                or args.dry_run
                or args.init_state
            ):
                raise ValueError("test message must be a standalone command")
            if not config.notifications.enabled:
                raise ValueError("notifications disabled")
            from .telegram import TelegramNotifier

            outcome = TelegramNotifier.from_environment(config.retry).send(
                "TEST — Doomsday Ticket Monitor\nPhase 5 Telegram integration test.\n"
                "This is not a ticket availability alert.\n"
                f"Sent: {now_ist():%d %b %Y, %I:%M %p} IST\n"
                f"Target: {config.target.movie}, {config.target.venue}, "
                f"{config.target.city}\n"
                f"Target date: {config.target.date}\nMovie: {config.district.movie_url}"
            )
            print(
                json.dumps(
                    {
                        "mode": "telegram_test",
                        "status": outcome.status,
                        "error": outcome.error,
                        "production_state_changed": False,
                    }
                )
            )
            return 0 if outcome.status == "accepted" else 4
        if args.send_pending or args.resolve_event:
            from .delivery import resolve_event

            store = production_store(args)
            if args.resolve_event:
                if not args.resolution:
                    raise ValueError("choose retry or accepted resolution")
                resolve_event(store, args.resolve_event, args.resolution)
                print(
                    json.dumps(
                        {
                            "event_resolved": args.resolve_event,
                            "resolution": args.resolution,
                        }
                    )
                )
                return 0
            report = send_queue(args, config)
            print(json.dumps(report, indent=2))
            return 4 if report["delivery_problems"] else 0
        if args.provider:
            if args.fixture or (
                not args.dry_run and not (args.state or args.state_repo)
            ):
                logger.error(
                    "Live checks require --dry-run or state; fixtures are separate"
                )
                return 2
            if args.provider != "all" and not config.providers.get(
                args.provider, False
            ):
                logger.error("Requested provider is disabled")
                return 2
            from .bookmyshow import BookMyShowProvider
            from .browser import fetch_page
            from .district import DistrictProvider

            settings = config.bookmyshow
            providers = {
                "bookmyshow": BookMyShowProvider(
                    settings.movie_url,
                    settings.cinema_url,
                    settings.movie_id,
                    settings.venue_id,
                    fetch_page,
                ),
                "district": DistrictProvider(config.district),
            }
            selected = [
                name
                for name in providers
                if config.providers.get(name, False) and args.provider in (name, "all")
            ]
            results = [
                providers[name].check_availability(config.target) for name in selected
            ]
            payload = {
                "mode": "live_read_only",
                "synthetic": False,
                "messages_sent": 0,
                "production_state_changed": False,
            }
            if args.provider == "all":
                payload["results"] = [r.model_dump(mode="json") for r in results]
            else:
                observed = results[0]
                payload["result"] = observed.model_dump(mode="json")
                payload["earliest_show"] = (
                    observed.earliest_show.model_dump(mode="json")
                    if observed.earliest_show
                    else None
                )
            if args.state or args.state_repo:
                payload.update(persist_results(results, args))
            if args.notify:
                payload.update(send_queue(args, config))
                payload.pop("messages_sent", None)
                payload.pop("pending_events", None)
            print(json.dumps(payload, indent=2))
            if payload.get("delivery_problems"):
                return 4
            return 1 if any(r.error for r in results) else 0

        if args.fixture is None or (not args.dry_run and not args.state):
            logger.error(
                "Full monitoring is not implemented. Use --dry-run with "
                "--fixture PATH or --provider bookmyshow."
            )
            return 2
        results = load_results(args.fixture, config)
        payload = preview(results, config)
        if args.state:
            payload.pop("assumption", None)
            payload.pop("intended_events", None)
            payload.update(persist_results(results, args))
        print(json.dumps(payload, indent=2))
        logger.info("Synthetic processing completed; no messages sent")
        return 0
    except StateError as error:
        logger.error("State operation failed: %s", error)
        return 3
    except ValidationError as error:
        # Do not log raw input values: misconfigured YAML may contain credentials.
        details = "; ".join(
            ".".join(str(part) for part in item["loc"]) + ": " + item["type"]
            for item in error.errors(include_input=False, include_context=False)
        )
        logger.error("Validation failed: %s", details)
    except (OSError, ValueError, YAMLError) as error:
        logger.error("Cannot load configuration or fixture (%s)", type(error).__name__)
    return 2
