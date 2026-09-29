"""Read District's public server-rendered data, without private APIs."""

import json
import ssl
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import truststore
from bs4 import BeautifulSoup

from .bookmyshow import CheckError, PageSnapshot, normalize
from .config import DistrictSettings, Target
from .models import MonitorState, Provider, ProviderResult, Show, ShowStatus
from .time_utils import IST, now_ist


def fetch_page(url: str) -> PageSnapshot:
    try:
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with urlopen(url, timeout=20, context=context) as response:
            return PageSnapshot(
                response.url, response.read(5_000_001).decode("utf-8"), response.status
            )
    except HTTPError as error:
        raise CheckError(f"HTTP_{error.code}") from None
    except (URLError, TimeoutError, OSError):
        raise CheckError("NETWORK_ERROR") from None


def page_data(snapshot: PageSnapshot, page_type: str) -> dict:
    if snapshot.status != 200:
        raise CheckError(f"HTTP_{snapshot.status}")
    parsed = urlparse(snapshot.url)
    if parsed.scheme != "https" or parsed.netloc != "www.district.in":
        raise CheckError("UNEXPECTED_REDIRECT")
    if len(snapshot.html) > 5_000_000:
        raise CheckError("RESPONSE_TOO_LARGE")
    soup = BeautifulSoup(snapshot.html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if script is None:
        raise CheckError("PAGE_DATA_MISSING")
    page = json.loads(script.get_text())["props"]["pageProps"]
    if page["type"] != page_type:
        raise CheckError("PAGE_TYPE_MISMATCH")
    return page["data"]


def result(
    target: Target,
    state: MonitorState,
    shows: list[Show] | None = None,
    error: str | None = None,
) -> ProviderResult:
    return ProviderResult(
        provider=Provider.DISTRICT,
        movie=target.movie,
        city=target.city,
        venue=target.venue,
        target_date=target.date,
        state=state,
        checked_at=now_ist(),
        shows=shows or [],
        error=error,
    )


def parse_movie(
    snapshot: PageSnapshot, target: Target, settings: DistrictSettings
) -> None:
    data = page_data(snapshot, "mdp_v2_page")
    movie = data["movieData"]["meta"]["movie"]
    if (
        urlparse(snapshot.url).path != urlparse(settings.movie_url).path
        or str(movie["content_id"]) != settings.movie_id
        or normalize(movie["name"]) != normalize(target.movie)
    ):
        raise CheckError("MOVIE_IDENTITY_MISMATCH")


def parse_schedule(
    snapshot: PageSnapshot, target: Target, settings: DistrictSettings
) -> ProviderResult:
    data = page_data(snapshot, "cdp_page")
    parsed = urlparse(snapshot.url)
    if parsed.path != urlparse(settings.cinema_url).path:
        raise CheckError("VENUE_URL_MISMATCH")
    if parse_qs(parsed.query).get("fromdate") != [target.date.isoformat()]:
        raise CheckError("SELECTED_DATE_MISMATCH")
    if str(data["cinemaId"]) != settings.venue_id or normalize(
        data["cityLabel"]
    ) != normalize(target.city):
        raise CheckError("VENUE_OR_CITY_MISMATCH")
    if list(data["serverState"]) != [settings.venue_id + target.date.isoformat()]:
        raise CheckError("SELECTED_DATE_MISMATCH")
    states = list(data["serverState"].values())
    if len(states) != 1:
        raise CheckError("SCHEDULE_AMBIGUOUS")
    schedule = states[0]
    cinema = schedule["meta"]["cinema"]
    aliases = {normalize(v) for v in [target.venue, *target.venue_aliases]}
    if (
        str(cinema["id"]) != settings.venue_id
        or normalize(cinema["name"]) not in aliases
    ):
        raise CheckError("VENUE_IDENTITY_MISMATCH")
    if schedule.get("arrangedSessions") == [] and "data" not in schedule:
        soup = BeautifulSoup(snapshot.html, "html.parser")
        if soup.find(
            string=lambda text: (
                text and text.strip() == "No shows playing at the moment"
            )
        ):
            return result(target, MonitorState.MOVIE_LISTED)
        raise CheckError("EMPTY_SCHEDULE_UNCONFIRMED")
    dates = schedule["data"]["sessionDates"]
    if not isinstance(dates, list) or not dates:
        raise CheckError("SCHEDULE_DATES_MISSING")
    for day in dates:
        datetime.strptime(day, "%Y-%m-%d")
    if target.date.isoformat() not in dates:
        return result(target, MonitorState.MOVIE_LISTED)
    groups = schedule["arrangedSessions"]
    if not isinstance(groups, list) or not groups:
        raise CheckError("SCHEDULE_EMPTY_OR_INCOMPLETE")
    shows = []
    for group in groups:
        if str(group["entityCode"]) != settings.movie_id:
            continue
        if (
            normalize(group["entityName"]) != normalize(target.movie)
            or str(group["cinemaId"]) != settings.venue_id
        ):
            raise CheckError("SHOW_IDENTITY_MISMATCH")
        if not group["sessions"]:
            raise CheckError("SHOWS_MISSING")
        for session in group["sessions"]:
            if (
                str(session["cid"]) != settings.venue_id
                or str(session["contentId"]) != settings.movie_id
            ):
                raise CheckError("SHOW_IDENTITY_MISMATCH")
            # District's naive payload times are UTC (verified against rendered IST).
            starts = datetime.fromisoformat(session["showTime"])
            starts = (
                starts.replace(tzinfo=timezone.utc) if starts.tzinfo is None else starts
            ).astimezone(IST)
            if starts.date() != target.date:
                raise CheckError("SHOW_DATE_MISMATCH")
            disabled, available = session["disableClick"], session["avail"]
            if (
                type(disabled) is not bool
                or type(available) is not int
                or available < 0
            ):
                raise CheckError("SHOW_STATUS_INVALID")
            status = {
                "Available": ShowStatus.AVAILABLE,
                "Filling Fast": ShowStatus.FAST_FILLING,
                "Sold Out": ShowStatus.SOLD_OUT,
            }.get(session["seatStatus"], ShowStatus.UNKNOWN)
            if status in (ShowStatus.AVAILABLE, ShowStatus.FAST_FILLING) and (
                disabled or available == 0
            ):
                status = ShowStatus.NOT_BOOKABLE
            shows.append(
                Show(starts_at=starts, status=status, booking_url=snapshot.url)
            )
    shows.sort(key=lambda show: show.starts_at)
    state = (
        MonitorState.FIRST_SHOW_AVAILABLE
        if any(s.bookable for s in shows)
        else MonitorState.TARGET_VENUE_AVAILABLE
        if shows
        else MonitorState.TARGET_DATE_AVAILABLE
    )
    return result(target, state, shows)


class DistrictProvider:
    def __init__(
        self,
        settings: DistrictSettings,
        fetch: Callable[[str], PageSnapshot] = fetch_page,
    ) -> None:
        self.settings = settings
        self.fetch = fetch

    def check_availability(self, target: Target) -> ProviderResult:
        try:
            parse_movie(self.fetch(self.settings.movie_url), target, self.settings)
            url = self.settings.cinema_url + "?fromdate=" + target.date.isoformat()
            return parse_schedule(self.fetch(url), target, self.settings)
        except CheckError as error:
            return result(target, MonitorState.CHECK_FAILED, error=str(error))
        except (KeyError, TypeError, ValueError, AttributeError):
            return result(target, MonitorState.CHECK_FAILED, error="SCHEMA_CHANGED")
        except Exception:
            return result(target, MonitorState.CHECK_FAILED, error="PROVIDER_ERROR")
