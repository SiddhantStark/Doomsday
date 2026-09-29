"""Durable observations and an outbox; no notification transport calls."""

import fcntl
import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import AwareDatetime, Field, model_validator

from .models import EventKind, Model, ProviderResult, Show
from .time_utils import now_ist


class StateError(ValueError):
    """Sanitized state failure. Never silently reset history."""


def target_key(result: ProviderResult) -> str:
    identity = [
        str(result.provider),
        result.movie.casefold(),
        result.city.casefold(),
        result.venue.casefold(),
        str(result.target_date),
    ]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


class Observation(Model):
    last_check: AwareDatetime
    last_success: ProviderResult | None = None
    failures: int = Field(default=0, ge=0)
    ever_available: bool = False


class OutboxEvent(Model):
    id: str = Field(min_length=1)
    target_key: str
    kind: EventKind
    observation: ProviderResult
    show: Show | None
    created_at: AwareDatetime
    status: Literal[
        "pending", "sending", "accepted", "failed", "uncertain", "skipped"
    ] = "pending"
    accepted_at: AwareDatetime | None = None
    attempts: int = Field(default=0, ge=0)
    last_error: str | None = None
    next_attempt_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def consistent(self) -> "OutboxEvent":
        if (self.status == "accepted") != (self.accepted_at is not None):
            raise ValueError("accepted events require acceptance timestamp")
        if self.target_key != target_key(self.observation):
            raise ValueError("event target mismatch")
        if self.kind == EventKind.HEALTH_WARNING:
            if not self.observation.error or self.show is not None:
                raise ValueError("health event requires a failed check")
        elif self.show is None or self.observation.error:
            raise ValueError("availability event requires a bookable show")
        if self.show != self.observation.earliest_show:
            raise ValueError("event show mismatch")
        return self


class State(Model):
    version: Literal[2] = 2
    namespace: Literal["production", "synthetic"]
    observations: dict[str, Observation] = Field(default_factory=dict)
    events: list[OutboxEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent(self) -> "State":
        if len({e.id for e in self.events}) != len(self.events):
            raise ValueError("duplicate event IDs")
        for key, item in self.observations.items():
            if item.last_success:
                if target_key(item.last_success) != key or item.last_success.error:
                    raise ValueError("invalid successful observation")
                if item.last_success.checked_at > item.last_check:
                    raise ValueError("observation timestamps reversed")
                if item.last_success.earliest_show and not item.ever_available:
                    raise ValueError("availability history inconsistent")
        if any(e.target_key not in self.observations for e in self.events):
            raise ValueError("orphan event")
        return self


def apply_results(state: State, results: list[ProviderResult]) -> list[OutboxEvent]:
    """Update a transaction copy; failed/stale checks cannot erase success."""
    keys = [target_key(r) for r in results]
    if len(keys) != len(set(keys)):
        raise StateError("DUPLICATE_TARGET")
    created = []
    for result in results:
        key = target_key(result)
        prior = state.observations.get(key)
        if prior and result.checked_at <= prior.last_check:
            continue
        previous = prior.last_success if prior else None
        ever = prior.ever_available if prior else False
        if result.error:
            state.observations[key] = Observation(
                last_check=result.checked_at,
                last_success=previous,
                failures=(prior.failures if prior else 0) + 1,
                ever_available=ever,
            )
            if state.observations[key].failures == 3:
                event = OutboxEvent(
                    id=str(uuid4()),
                    target_key=key,
                    kind=EventKind.HEALTH_WARNING,
                    observation=result,
                    show=None,
                    created_at=now_ist(),
                )
                state.events.append(event)
                created.append(event)
            continue
        show = result.earliest_show
        old_show = previous.earliest_show if previous else None
        kind = None
        # Unknown statuses are not evidence of genuine disappearance.
        uncertain = not show and any(s.status == "UNKNOWN" for s in result.shows)
        if show:
            if not ever:
                kind = EventKind.BOOKING_OPENED
            elif old_show is None:
                kind = EventKind.AVAILABILITY_REAPPEARED
            elif show.starts_at < old_show.starts_at:
                kind = EventKind.EARLIER_SHOW_ADDED
        if kind:
            event = OutboxEvent(
                id=str(uuid4()),
                target_key=key,
                kind=kind,
                observation=result,
                show=show,
                created_at=now_ist(),
            )
            state.events.append(event)
            created.append(event)
        state.observations[key] = Observation(
            last_check=result.checked_at,
            last_success=previous if uncertain else result,
            ever_available=ever or show is not None,
        )
    return created


def mark_accepted(state: State, event_id: str) -> None:
    """Record API acceptance only; never persist private transport identifiers."""
    event = next((e for e in state.events if e.id == event_id), None)
    if event is None:
        raise StateError("EVENT_NOT_FOUND")
    if event.status in ("pending", "sending"):
        event.status = "accepted"
        event.accepted_at = now_ist()


class JsonStore:
    def __init__(
        self, path: Path, namespace: Literal["production", "synthetic"]
    ) -> None:
        self.path = path
        self.namespace = namespace

    def read(self) -> State:
        try:
            raw = json.loads(self.path.read_text())
            if not isinstance(raw, dict) or set(raw) != {
                "version",
                "namespace",
                "observations",
                "events",
            }:
                raise ValueError("incomplete state")
            if raw["version"] == 1:
                # Lossless v1 migration, committed only on a writable transaction.
                legacy_fields = set(OutboxEvent.model_fields) - {
                    "attempts",
                    "last_error",
                    "next_attempt_at",
                }
                for item in raw["events"]:
                    if set(item) != legacy_fields or item["status"] not in (
                        "pending",
                        "accepted",
                    ):
                        raise ValueError("invalid legacy event")
                    item.update(attempts=0, last_error=None, next_attempt_at=None)
                raw["version"] = 2
            for item in raw["observations"].values():
                if set(item) != set(Observation.model_fields):
                    raise ValueError("incomplete observation")
            for item in raw["events"]:
                if set(item) != set(OutboxEvent.model_fields):
                    raise ValueError("incomplete event")
            state = State.model_validate(raw)
        except FileNotFoundError:
            raise StateError("STATE_MISSING_USE_INIT_STATE") from None
        except (OSError, ValueError, TypeError, AttributeError):
            raise StateError("STATE_UNREADABLE_OR_CORRUPT") from None
        if state.namespace != self.namespace:
            raise StateError("STATE_NAMESPACE_MISMATCH")
        return state

    def write(self, state: State) -> None:
        state = State.model_validate(state.model_dump())
        if state.namespace != self.namespace:
            raise StateError("STATE_NAMESPACE_MISMATCH")
        payload = state.model_dump_json(indent=2) + "\n"
        if self.path.exists() and self.path.read_text() == payload:
            return
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=self.path.parent, prefix=".state-", delete=False
            ) as file:
                temporary = Path(file.name)
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            raise StateError("STATE_WRITE_FAILED") from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @contextmanager
    def transaction(
        self, initialize: bool = False, readonly: bool = False
    ) -> Iterator[State]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(self.path.suffix + ".lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise StateError("STATE_LOCKED") from None
            try:
                if initialize:
                    if self.path.exists() or readonly:
                        raise StateError("STATE_ALREADY_EXISTS_OR_INIT_DRY_RUN")
                    state = State(namespace=self.namespace)
                else:
                    state = self.read()
                yield state
                if not readonly:
                    self.write(state)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
