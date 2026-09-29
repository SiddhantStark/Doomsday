import json
from datetime import date
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from doomsday import cli
from doomsday.bookmyshow import CheckError, PageSnapshot
from doomsday.config import DistrictSettings, load_config
from doomsday.district import DistrictProvider, parse_schedule, result
from doomsday.models import MonitorState

FIXTURES = Path("tests/fixtures/district")


def setup_schedule():
    config = load_config(Path("config/monitor.yml"))
    soup = BeautifulSoup((FIXTURES / "venue.html").read_text(), "html.parser")
    data = json.loads(soup.script.string)
    group = next(iter(data["props"]["pageProps"]["data"]["serverState"].values()))[
        "arrangedSessions"
    ][0]
    target = config.target.model_copy(
        update={"movie": group["entityName"], "date": date(2026, 9, 28)}
    )
    settings = config.district.model_copy(update={"movie_id": str(group["entityCode"])})
    return target, settings, data


def snapshot(settings, target, data):
    return PageSnapshot(
        settings.cinema_url + "?fromdate=" + str(target.date),
        '<script id="__NEXT_DATA__">' + json.dumps(data) + "</script>",
    )


def test_observed_schedule_utc_conversion():
    target, settings, data = setup_schedule()
    observed = parse_schedule(snapshot(settings, target, data), target, settings)
    assert observed.state == MonitorState.FIRST_SHOW_AVAILABLE
    assert observed.earliest_show.starts_at.strftime("%H:%M") == "22:20"
    assert [s.starts_at.strftime("%H:%M") for s in observed.shows] == [
        "22:20",
    ]


@pytest.mark.parametrize(
    "status,disabled,avail,bookable",
    [
        ("Sold Out", True, 0, False),
        ("Available", True, 10, False),
        ("Available", False, 0, False),
        ("New Status", False, 10, False),
        ("Filling Fast", False, 10, True),
    ],
)
def test_statuses(status, disabled, avail, bookable):
    target, settings, data = setup_schedule()
    schedule = next(iter(data["props"]["pageProps"]["data"]["serverState"].values()))
    for session in schedule["arrangedSessions"][0]["sessions"]:
        session.update(seatStatus=status, disableClick=disabled, avail=avail)
    observed = parse_schedule(snapshot(settings, target, data), target, settings)
    assert bool(observed.earliest_show) == bookable


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("cid", 999, "SHOW_IDENTITY_MISMATCH"),
        ("contentId", 999, "SHOW_IDENTITY_MISMATCH"),
        ("showTime", "2026-09-28T23:00", "SHOW_DATE_MISMATCH"),
        ("disableClick", "false", "SHOW_STATUS_INVALID"),
    ],
)
def test_invalid_sessions(field, value, error):
    target, settings, data = setup_schedule()
    schedule = next(iter(data["props"]["pageProps"]["data"]["serverState"].values()))
    schedule["arrangedSessions"][0]["sessions"][0][field] = value
    with pytest.raises(CheckError, match=error):
        parse_schedule(snapshot(settings, target, data), target, settings)


def test_real_empty_target():
    config = load_config(Path("config/monitor.yml"))

    def fetch(url):
        filename = "movie" if "-MV" in url else "empty"
        return PageSnapshot(url, (FIXTURES / (filename + ".html")).read_text())

    observed = DistrictProvider(config.district, fetch).check_availability(
        config.target
    )
    assert observed.state == MonitorState.MOVIE_LISTED
    assert not observed.shows


@pytest.mark.parametrize(
    "html,status",
    [
        ("<html>Blocked</html>", 403),
        ("oops", 200),
        ('<script id="__NEXT_DATA__">{}</script>', 200),
    ],
)
def test_failure_is_not_unavailability(html, status):
    config = load_config(Path("config/monitor.yml"))
    provider = DistrictProvider(
        config.district, lambda url: PageSnapshot(url, html, status)
    )
    assert provider.check_availability(config.target).state == MonitorState.CHECK_FAILED


def test_both_providers_isolated(monkeypatch, capsys):
    from doomsday.bookmyshow import BookMyShowProvider
    from doomsday.bookmyshow import result as bms_result

    monkeypatch.setattr(
        BookMyShowProvider,
        "check_availability",
        lambda self, target: bms_result(
            target, MonitorState.CHECK_FAILED, error="HTTP_403"
        ),
    )
    monkeypatch.setattr(
        DistrictProvider,
        "check_availability",
        lambda self, target: result(target, MonitorState.MOVIE_LISTED),
    )
    assert cli.main(["--dry-run", "--provider", "all"]) == 1
    output = json.loads(capsys.readouterr().out)
    assert [r["state"] for r in output["results"]] == ["CHECK_FAILED", "MOVIE_LISTED"]
    assert output["messages_sent"] == 0


def test_official_url_validation():
    with pytest.raises(ValueError):
        DistrictSettings(movie_url="https://example.com/-MV176735")


@pytest.mark.parametrize(
    "change,error",
    [
        ("city", "VENUE_OR_CITY_MISMATCH"),
        ("venue", "VENUE_IDENTITY_MISMATCH"),
        ("date", "SELECTED_DATE_MISMATCH"),
        ("movie", "SHOW_IDENTITY_MISMATCH"),
    ],
)
def test_identity_guards(change, error):
    target, settings, data = setup_schedule()
    page = data["props"]["pageProps"]["data"]
    schedule = next(iter(page["serverState"].values()))
    if change == "city":
        page["cityLabel"] = "Mumbai"
    elif change == "venue":
        schedule["meta"]["cinema"]["name"] = "Other Cinema"
    elif change == "movie":
        schedule["arrangedSessions"][0]["entityName"] = "Other Movie"
    else:
        page["serverState"] = {"95052026-09-29": schedule}
    with pytest.raises(CheckError, match=error):
        parse_schedule(snapshot(settings, target, data), target, settings)


def test_earliest_excludes_sold_out():
    target, settings, data = setup_schedule()
    schedule = next(iter(data["props"]["pageProps"]["data"]["serverState"].values()))
    group = schedule["arrangedSessions"][0]
    base = group["sessions"][0]
    group["sessions"] = [
        dict(base, showTime="2026-09-28T08:00", seatStatus="Sold Out", avail=0),
        dict(base, showTime="2026-09-28T11:25"),
        base,
    ]
    observed = parse_schedule(snapshot(settings, target, data), target, settings)
    assert observed.earliest_show.starts_at.strftime("%H:%M") == "16:55"


def test_transport_failure():
    config = load_config(Path("config/monitor.yml"))

    def fail(url):
        raise CheckError("NETWORK_ERROR")

    observed = DistrictProvider(config.district, fail).check_availability(config.target)
    assert observed.error == "NETWORK_ERROR"
