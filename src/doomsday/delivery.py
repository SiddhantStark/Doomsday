"""Claim durably before sending, then persist the sanitized delivery outcome."""

from datetime import timedelta

from .config import Config
from .git_state import GitStore
from .models import EventKind
from .state import JsonStore, StateError, mark_accepted, target_key
from .telegram import TelegramNotifier, format_event
from .time_utils import now_ist


def deliver_pending(
    store: JsonStore | GitStore, notifier: TelegramNotifier, config: Config
) -> dict:
    accepted = 0
    problems = []
    if not config.notifications.enabled:
        return {
            "messages_accepted": 0,
            "delivery_problems": [],
            "delivery_disabled": True,
        }
    # Each claim is a committed transaction before the external side effect.
    # A crash after claiming leaves 'sending', requiring operator resolution.
    with store.transaction() as state:
        if state.namespace != "production":
            raise StateError("SYNTHETIC_DELIVERY_FORBIDDEN")
        candidates = [
            e.id for e in state.events if e.status not in ("accepted", "skipped")
        ]
    for event_id in candidates[:20]:
        claimed = None
        with store.transaction() as state:
            event = next(e for e in state.events if e.id == event_id)
            if event.status in ("sending", "uncertain", "failed"):
                problems.append(
                    {
                        "event_id": event.id,
                        "error": event.last_error or "DELIVERY_REQUIRES_REVIEW",
                    }
                )
                continue
            if event.status != "pending":
                continue
            if event.next_attempt_at and event.next_attempt_at > now_ist():
                problems.append({"event_id": event.id, "error": "RETRY_DEFERRED"})
                break
            target = config.target
            observed = event.observation
            if (
                observed.movie != target.movie
                or observed.city != target.city
                or observed.venue != target.venue
                or observed.target_date != target.date
                or not config.providers.get(observed.provider, False)
            ):
                # Other targets and disabled providers remain queued.
                continue
            latest = state.observations[event.target_key]
            stale = event.show is not None and (
                event.show.starts_at <= now_ist()
                or latest.last_success is None
                or latest.last_success.earliest_show is None
                or latest.last_success.earliest_show.starts_at != event.show.starts_at
            )
            if event.kind == EventKind.STATUS_SUMMARY:
                if not config.notifications.status_summaries:
                    continue
                stale = any(
                    not config.providers.get(r.provider, False)
                    or target_key(r) not in state.observations
                    or state.observations[target_key(r)].last_check > r.checked_at
                    for r in event.report_results
                )
            elif event.show is None:
                stale = latest.failures < 3
            if stale:
                event.status = "skipped"
                event.last_error = "SUPERSEDED_OR_EXPIRED"
                continue
            event.status = "sending"
            event.attempts += 1
            event.last_error = None
            event.next_attempt_at = None
            claimed = event.model_copy(deep=True)
        if claimed is None:
            continue
        outcome = notifier.send(format_event(claimed))
        with store.transaction() as state:
            event = next(e for e in state.events if e.id == event_id)
            if event.status != "sending":
                raise StateError("DELIVERY_CLAIM_CHANGED")
            if outcome.status == "accepted":
                mark_accepted(state, event_id)
                accepted += 1
            else:
                event.status = outcome.status
                event.last_error = outcome.error
                if outcome.status == "pending":
                    event.next_attempt_at = now_ist() + timedelta(
                        seconds=outcome.retry_after
                    )
                problems.append({"event_id": event.id, "error": outcome.error})
        if outcome.status != "accepted":
            break
    return {"messages_accepted": accepted, "delivery_problems": problems}


def resolve_event(store: JsonStore | GitStore, event_id: str, resolution: str) -> None:
    with store.transaction() as state:
        event = next((e for e in state.events if e.id == event_id), None)
        if event is None or event.status not in ("sending", "uncertain", "failed"):
            raise StateError("EVENT_NOT_RESOLVABLE")
        if resolution not in ("retry", "accepted"):
            raise StateError("INVALID_RESOLUTION")
        event.status = "pending"
        event.last_error = None
        event.next_attempt_at = None
        if resolution == "accepted":
            mark_accepted(state, event_id)
