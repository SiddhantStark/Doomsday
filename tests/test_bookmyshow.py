from datetime import date
from pathlib import Path

import pytest

from doomsday.bookmyshow import (
    BookMyShowProvider,
    CheckError,
    PageSnapshot,
    parse_movie,
    parse_schedule,
)
from doomsday.config import BookMyShowSettings, load_config
from doomsday.models import MonitorState, ProviderResult, ShowStatus

CONFIG = load_config(Path("config/monitor.yml"))
SETTINGS = CONFIG.bookmyshow
ROOT = Path("tests/fixtures/bookmyshow")
URL = SETTINGS.cinema_url + "/20260928"
HTML = (ROOT / "venue.html").read_text()
TARGET = CONFIG.target.model_copy(
    update={"movie": "Heart of the Beast", "date": date(2026, 9, 28)}
)


def parse(html: str = HTML, url: str = URL) -> ProviderResult:
    return parse_schedule(PageSnapshot(url, html), TARGET, "ET00504928", "CBMC")


def test_observed_movie_and_venue_fragments() -> None:
    state = parse_movie(
        PageSnapshot(SETTINGS.movie_url, (ROOT / "coming_soon.html").read_text()),
        CONFIG.target,
        SETTINGS.movie_id,
    )
    assert state == MonitorState.COMING_SOON
    observed = parse()
    assert observed.state == MonitorState.FIRST_SHOW_AVAILABLE
    assert observed.earliest_show.starts_at.hour == 22
    assert str(observed.earliest_show.booking_url) == URL


@pytest.mark.parametrize(
    "old,new",
    [
        ("Mon</span>", "Tue</span>"),
        ("28</span>", "29</span>"),
        ("Cinepolis: BSR Mall, OMR, Thoraipakkam", "Other Cinema"),
        ("Heart of the Beast (UA16+)", "Avengers Endgame (UA16+)"),
        ("10:20 PM", "99:99 PM"),
        ('role="grid"', 'role="unknown"'),
        ('aria-label="Book 10:20 PM"', 'aria-label="Unknown"'),
    ],
)
def test_markup_and_identity_errors(old: str, new: str) -> None:
    with pytest.raises(CheckError):
        parse(HTML.replace(old, new))


@pytest.mark.parametrize(
    "url",
    [
        URL.replace("20260928", "20270928"),
        URL.replace("chennai", "mumbai"),
        URL.replace("CBMC", "OTHER"),
        URL.replace("in.bookmyshow.com", "example.com"),
    ],
)
def test_wrong_page_rejected(url: str) -> None:
    with pytest.raises(CheckError):
        parse(url=url)


def test_disabled_show_not_bookable() -> None:
    observed = parse(
        HTML.replace('aria-label="Book', 'aria-disabled="true" aria-label="Book')
    )
    assert observed.earliest_show is None
    assert observed.shows[0].status == ShowStatus.NOT_BOOKABLE


def test_earliest_time_is_sorted_and_unknown_color_not_used() -> None:
    extra = '<button aria-label="Book 09:00" disabled>09:00</button>'
    extra += '<button aria-label="Book 12:00 AM">12:00 AM</button>'
    html = HTML.replace("<div color=", extra + "<div color=")
    observed = parse(html)
    assert observed.earliest_show.starts_at.hour == 0
    assert len(observed.shows) == 3


@pytest.mark.parametrize(
    "status,body",
    [(403, ""), (200, "Verify you are human"), (200, "<div>changed page</div>")],
)
def test_failures_normalized(status: int, body: str) -> None:
    provider = BookMyShowProvider(
        SETTINGS.movie_url,
        SETTINGS.cinema_url,
        SETTINGS.movie_id,
        SETTINGS.venue_id,
        lambda url: PageSnapshot(url, body, status),
    )
    observed = provider.check_availability(CONFIG.target)
    assert observed.state == MonitorState.CHECK_FAILED
    assert observed.error
    assert observed.earliest_show is None


def test_coming_soon_does_not_request_schedule() -> None:
    calls = []

    def fetch(url: str) -> PageSnapshot:
        calls.append(url)
        return PageSnapshot(url, (ROOT / "coming_soon.html").read_text())

    provider = BookMyShowProvider(
        SETTINGS.movie_url,
        SETTINGS.cinema_url,
        SETTINGS.movie_id,
        SETTINGS.venue_id,
        fetch,
    )
    assert provider.check_availability(CONFIG.target).state == MonitorState.COMING_SOON
    assert calls == [SETTINGS.movie_url]


def test_open_movie_requests_exact_target_date() -> None:
    movie_url = "https://in.bookmyshow.com/movies/chennai/heart-of-the-beast/ET00504928"
    calls = []

    def fetch(url: str) -> PageSnapshot:
        calls.append(url)
        html = (
            (
                '<div id="main-content"><h1>Heart of the Beast</h1>'
                "<button>Book tickets</button></div>"
            )
            if url == movie_url
            else HTML
        )
        return PageSnapshot(url, html)

    provider = BookMyShowProvider(
        movie_url, SETTINGS.cinema_url, "ET00504928", "CBMC", fetch
    )
    assert provider.check_availability(TARGET).earliest_show
    assert calls == [movie_url, URL]


def test_transport_error_redacted() -> None:
    def fetch(url: str) -> PageSnapshot:
        raise RuntimeError("secret browser details")

    provider = BookMyShowProvider(
        SETTINGS.movie_url,
        SETTINGS.cinema_url,
        SETTINGS.movie_id,
        SETTINGS.venue_id,
        fetch,
    )
    assert provider.check_availability(CONFIG.target).error == "PROVIDER_ERROR"


def test_external_config_url_rejected() -> None:
    with pytest.raises(ValueError):
        BookMyShowSettings(movie_url="https://example.com/ET00439706")


def test_no_matching_movie_is_not_available() -> None:
    observed = parse_schedule(
        PageSnapshot(URL, HTML),
        CONFIG.target.model_copy(update={"date": date(2026, 9, 28)}),
        SETTINGS.movie_id,
        SETTINGS.venue_id,
    )
    assert observed.state == MonitorState.TARGET_DATE_AVAILABLE
    assert observed.earliest_show is None


def test_live_cli_reports_failure_without_fixture_claim(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    import json

    from doomsday import browser
    from doomsday.cli import main

    monkeypatch.setattr(browser, "fetch_page", lambda url: PageSnapshot(url, "", 403))
    assert main(["--once", "--dry-run", "--provider", "bookmyshow"]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["synthetic"] is False
    assert output["result"]["error"] == "HTTP_403"
    assert output["messages_sent"] == 0
