"""Conservative parser for BookMyShow's observed cinema schedule DOM."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .config import Target
from .models import MonitorState, Provider, ProviderResult, Show, ShowStatus
from .time_utils import IST, now_ist

HOST = "https://in.bookmyshow.com"


def normalize(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


@dataclass(frozen=True)
class PageSnapshot:
    url: str
    html: str
    status: int = 200


class CheckError(ValueError):
    """A sanitized provider diagnostic, safe for public output."""


def page_root(snapshot: PageSnapshot) -> BeautifulSoup:
    if snapshot.status >= 400:
        raise CheckError(f"HTTP_{snapshot.status}")
    parsed = urlparse(snapshot.url)
    if parsed.scheme != "https" or parsed.netloc != "in.bookmyshow.com":
        raise CheckError("UNEXPECTED_REDIRECT")
    soup = BeautifulSoup(snapshot.html, "html.parser")
    text = soup.get_text(" ", strip=True).casefold()
    if any(
        marker in text
        for marker in (
            "verify you are human",
            "access denied",
            "just a moment",
            "unusual traffic",
            "checking your browser",
        )
    ) or soup.select_one('iframe[src*="captcha"], #challenge-form'):
        raise CheckError("ACCESS_BLOCKED")
    return soup


def result(
    target: Target,
    state: MonitorState,
    shows: list[Show] | None = None,
    error: str | None = None,
) -> ProviderResult:
    return ProviderResult(
        provider=Provider.BOOKMYSHOW,
        movie=target.movie,
        city=target.city,
        venue=target.venue,
        target_date=target.date,
        state=state,
        checked_at=now_ist(),
        shows=shows or [],
        error=error,
    )


def parse_movie(snapshot: PageSnapshot, target: Target, movie_id: str) -> MonitorState:
    soup = page_root(snapshot)
    path = urlparse(snapshot.url).path.rstrip("/")
    if (
        not path.endswith("/" + movie_id)
        or f"/movies/{target.city.casefold()}/" not in path
    ):
        raise CheckError("MOVIE_URL_MISMATCH")
    heading = soup.find("h1")
    if heading is None or normalize(heading.get_text()) != normalize(target.movie):
        raise CheckError("MOVIE_IDENTITY_MISMATCH")
    main = soup.select_one("#main-content")
    if main is None:
        raise CheckError("MOVIE_MARKUP_CHANGED")
    text = main.get_text(" ", strip=True).casefold()
    controls = main.select('button, [role="button"], a')
    if any(c.get_text(" ", strip=True).casefold() == "book tickets" for c in controls):
        return MonitorState.BOOKING_OPEN
    if "mark interested to know when bookings open" in text:
        return MonitorState.COMING_SOON
    raise CheckError("MOVIE_STATUS_UNKNOWN")


def parse_schedule(
    snapshot: PageSnapshot, target: Target, movie_id: str, venue_id: str
) -> ProviderResult:
    soup = page_root(snapshot)
    path = urlparse(snapshot.url).path.rstrip("/")
    if f"/cinemas/{target.city.casefold()}/" not in path:
        raise CheckError("CITY_MISMATCH")
    if not path.endswith(f"/buytickets/{venue_id}/{target.date:%Y%m%d}"):
        raise CheckError("VENUE_OR_DATE_URL_MISMATCH")
    main = soup.find("main")
    if main is None:
        raise CheckError("SCHEDULE_MARKUP_CHANGED")
    aliases = {normalize(v) for v in [target.venue, *target.venue_aliases]}
    # Restrict identity evidence to the main body, never footer recommendations.
    if not any(normalize(s.get_text()) in aliases for s in main.find_all("span")):
        raise CheckError("VENUE_IDENTITY_MISMATCH")
    selected = main.select('[aria-pressed="true"]')
    expected = target.date.strftime("%a %d %b").casefold()
    if not any(s.get_text(" ", strip=True).casefold() == expected for s in selected):
        raise CheckError("SELECTED_DATE_MISMATCH")
    grid = main.select_one('[role="grid"]')
    if grid is None:
        raise CheckError("SCHEDULE_GRID_MISSING")
    links = grid.select('a[href*="/movies/"]')
    if not links:
        raise CheckError("SCHEDULE_EMPTY_OR_INCOMPLETE")
    shows: list[Show] = []
    matched = False
    for link in links:
        if (
            not urlparse(str(link.get("href")))
            .path.rstrip("/")
            .endswith("/" + movie_id)
        ):
            continue
        title = re.sub(r"\s*\((?:UA\d*\+?|U|A|S)\)\s*$", "", link.get_text())
        if normalize(title) != normalize(target.movie):
            raise CheckError("SHOW_MOVIE_IDENTITY_MISMATCH")
        matched = True
        group = link.parent
        # Find the nearest movie group with show controls, without crossing
        # into a container holding multiple movie links.
        while group is not None and group is not grid:
            if len(group.select('a[href*="/movies/"]')) > 1:
                raise CheckError("SHOW_GROUP_AMBIGUOUS")
            if group.select('[aria-label^="Book "]'):
                break
            group = group.parent
        if group is None or group is grid:
            raise CheckError("SHOW_CONTROLS_MISSING")
        for control in group.select('[aria-label^="Book "]'):
            label = str(control["aria-label"])[5:].strip()
            parsed_time = None
            for fmt in ("%I:%M %p", "%H:%M"):
                try:
                    parsed_time = datetime.strptime(label, fmt).time()
                    break
                except ValueError:
                    continue
            if parsed_time is None:
                raise CheckError("MALFORMED_SHOWTIME")
            disabled = any(
                node.has_attr("disabled") or node.get("aria-disabled") == "true"
                for node in [control, *list(control.parents)[:3]]
            )
            if control.get("role") != "button" and control.name != "button":
                raise CheckError("UNKNOWN_SHOW_CONTROL")
            status = ShowStatus.NOT_BOOKABLE if disabled else ShowStatus.AVAILABLE
            shows.append(
                Show(
                    starts_at=datetime.combine(target.date, parsed_time, IST),
                    status=status,
                    booking_url=snapshot.url,
                )
            )
    if not matched:
        return result(target, MonitorState.TARGET_DATE_AVAILABLE)
    shows.sort(key=lambda show: show.starts_at)
    state = (
        MonitorState.FIRST_SHOW_AVAILABLE
        if any(s.bookable for s in shows)
        else MonitorState.TARGET_VENUE_AVAILABLE
    )
    return result(target, state, shows)


class BookMyShowProvider:
    def __init__(
        self,
        movie_url: str,
        cinema_url: str,
        movie_id: str,
        venue_id: str,
        fetch: Callable[[str], PageSnapshot],
    ) -> None:
        self.movie_url = movie_url
        self.cinema_url = cinema_url
        self.movie_id = movie_id
        self.venue_id = venue_id
        self.fetch = fetch

    def check_availability(self, target: Target) -> ProviderResult:
        try:
            movie = self.fetch(self.movie_url)
            state = parse_movie(movie, target, self.movie_id)
            if state == MonitorState.COMING_SOON:
                return result(target, state)
            url = self.cinema_url.rstrip("/") + f"/{target.date:%Y%m%d}"
            return parse_schedule(self.fetch(url), target, self.movie_id, self.venue_id)
        except CheckError as error:
            return result(target, MonitorState.CHECK_FAILED, error=str(error))
        except Exception:
            # Do not expose browser/network exceptions containing URLs or payloads.
            return result(target, MonitorState.CHECK_FAILED, error="PROVIDER_ERROR")
