"""Telegram transport with sanitized outcomes and no persisted message IDs."""

import json
import os
import re
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

import truststore

from .config import Retry
from .models import EventKind
from .state import OutboxEvent
from .time_utils import IST


@dataclass(frozen=True)
class SendOutcome:
    status: Literal["accepted", "pending", "failed", "uncertain"]
    error: str | None = None
    retry_after: int = 0


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post(token: str, payload: dict) -> tuple[int, dict]:
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = build_opener(
        NoRedirect(),
        HTTPSHandler(context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)),
    )
    try:
        response = opener.open(request, timeout=20)
    except HTTPError as error:
        response = error
    with response:
        code = response.code
        try:
            body = json.loads(response.read(100_000))
        except (ValueError, UnicodeError):
            body = {}
    return code, body


def format_event(event: OutboxEvent) -> str:
    observation = event.observation
    title = {
        EventKind.BOOKING_OPENED: "Tickets available",
        EventKind.EARLIER_SHOW_ADDED: "Earlier show available",
        EventKind.AVAILABILITY_REAPPEARED: "Tickets available again",
        EventKind.HEALTH_WARNING: "Monitoring health warning",
    }[event.kind]
    lines = [
        title,
        observation.movie,
        f"{observation.venue}, {observation.city}",
        f"Platform: {observation.provider.value}",
        f"Target date: {observation.target_date:%d %b %Y}",
    ]
    if event.show:
        lines += [
            "Earliest bookable show: "
            f"{event.show.starts_at.astimezone(IST):%d %b %Y, %I:%M %p} IST"
        ]
        if event.show.booking_url:
            lines.append(f"Book: {event.show.booking_url}")
    else:
        lines.append("Three consecutive checks failed. Ticket availability is unknown.")
    lines += [
        f"Checked: {observation.checked_at.astimezone(IST):%d %b %Y, %I:%M %p} IST",
        f"Event: {event.id}",
    ]
    return "\n".join(lines)


class TelegramNotifier:
    def __init__(
        self,
        token: str,
        chat_id: str,
        retry: Retry | None = None,
        transport: Callable[[str, dict], tuple[int, dict]] = post,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token) or not re.fullmatch(
            r"-?\d+", chat_id
        ):
            raise ValueError("TELEGRAM_CREDENTIALS_MISSING_OR_INVALID")
        self.token = token
        self.chat_id = chat_id
        self.retry = retry or Retry()
        self.transport = transport
        self.sleep = sleep

    @classmethod
    def from_environment(cls, retry: Retry | None = None) -> "TelegramNotifier":
        return cls(
            os.getenv("TELEGRAM_BOT_TOKEN", ""),
            os.getenv("TELEGRAM_CHAT_ID", ""),
            retry,
        )

    def send(self, text: str) -> SendOutcome:
        if not text or len(text.encode("utf-16-le")) // 2 > 4096:
            return SendOutcome("failed", "MESSAGE_LENGTH_INVALID")
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "allow_paid_broadcast": False,
            "link_preview_options": {"is_disabled": True},
        }
        for attempt in range(self.retry.attempts):
            try:
                code, body = self.transport(self.token, payload)
            except Exception:
                # A timeout can occur after acceptance. Never retry blindly.
                return SendOutcome("uncertain", "TRANSPORT_OUTCOME_UNKNOWN")
            if not isinstance(body, dict):
                return SendOutcome("uncertain", "RESPONSE_INVALID")
            if code == 200 and body.get("ok") is True:
                # Inspect only the acceptance envelope; discard response IDs.
                if (
                    isinstance(body.get("result"), dict)
                    and type(body["result"].get("message_id")) is int
                ):
                    return SendOutcome("accepted")
                return SendOutcome("uncertain", "RESPONSE_INVALID")
            error_code = body.get("error_code", code)
            if error_code in (400, 401, 403, 404):
                return SendOutcome("failed", f"TELEGRAM_{error_code}")
            if body.get("ok") is not False:
                return SendOutcome("uncertain", "RESPONSE_INVALID")
            delay = (
                self.retry.backoff_seconds[
                    min(attempt, len(self.retry.backoff_seconds) - 1)
                ]
                if self.retry.backoff_seconds
                else 5
            )
            if error_code == 429:
                parameters = body.get("parameters")
                wait = (
                    parameters.get("retry_after")
                    if isinstance(parameters, dict)
                    else None
                )
                if type(wait) is not int or wait < 0:
                    return SendOutcome("failed", "RATE_LIMIT_RESPONSE_INVALID")
                delay = max(1, wait)
            elif type(error_code) is not int or error_code < 500:
                return SendOutcome("failed", "TELEGRAM_REJECTED")
            if attempt + 1 == self.retry.attempts or delay > 60:
                return SendOutcome(
                    "pending",
                    "RATE_LIMITED" if error_code == 429 else "TELEGRAM_UNAVAILABLE",
                    delay,
                )
            self.sleep(delay)
        raise AssertionError("unreachable")
