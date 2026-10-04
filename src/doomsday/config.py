"""Non-secret YAML configuration; unknown fields are rejected."""

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from .models import Model, Provider


class Target(Model):
    movie: str = Field(min_length=1)
    city: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    venue_aliases: list[str] = Field(min_length=1)
    date: date
    timezone: Literal["Asia/Kolkata"] = "Asia/Kolkata"
    show_strategy: Literal["EARLIEST_AVAILABLE"] = "EARLIEST_AVAILABLE"

    @model_validator(mode="after")
    def nonempty_aliases(self) -> "Target":
        if any(not alias.strip() for alias in self.venue_aliases):
            raise ValueError("venue aliases must not be empty")
        return self


class Retry(Model):
    attempts: int = Field(default=3, ge=1, le=5)
    backoff_seconds: list[int] = Field(default_factory=lambda: [5, 15])

    @model_validator(mode="after")
    def valid_backoff(self) -> "Retry":
        if len(self.backoff_seconds) != self.attempts - 1:
            raise ValueError("one backoff delay required between each attempt")
        if any(delay < 0 or delay > 300 for delay in self.backoff_seconds):
            raise ValueError("backoff must be between 0 and 300 seconds")
        return self


class ScheduleBand(Model):
    start: date
    interval_minutes: int = Field(ge=60, le=10080)


class Monitor(Model):
    interval_minutes: int = Field(default=60, ge=60, le=10080)
    schedule_bands: list[ScheduleBand] = Field(default_factory=list)

    @model_validator(mode="after")
    def ordered_bands(self) -> "Monitor":
        starts = [band.start for band in self.schedule_bands]
        if starts != sorted(set(starts)):
            raise ValueError("schedule bands must have unique ascending start dates")
        return self

    def interval_on(self, day: date) -> int:
        interval = self.interval_minutes
        for band in self.schedule_bands:
            if day >= band.start:
                interval = band.interval_minutes
        return interval


class Notifications(Model):
    status_summaries: bool = False
    channel: Literal["telegram"] = "telegram"
    enabled: bool = True
    allow_paid_broadcast: Literal[False] = False


class BookMyShowSettings(Model):
    movie_url: str = (
        "https://in.bookmyshow.com/movies/chennai/avengers-doomsday/ET00439706"
    )
    cinema_url: str = "https://in.bookmyshow.com/cinemas/chennai/cinepolis-bsr-mall-omr-thoraipakkam/buytickets/CBMC"
    movie_id: str = Field(default="ET00439706", pattern=r"^ET[0-9]+$")
    venue_id: str = Field(default="CBMC", pattern=r"^[A-Z0-9]+$")

    @model_validator(mode="after")
    def official_urls(self) -> "BookMyShowSettings":
        from urllib.parse import urlparse

        for url in (self.movie_url, self.cinema_url):
            parsed = urlparse(url)
            if (
                parsed.scheme != "https"
                or parsed.netloc != "in.bookmyshow.com"
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("BookMyShow URLs must use the official HTTPS host")
        if not self.movie_url.endswith("/" + self.movie_id):
            raise ValueError("movie URL must end with the configured movie ID")
        if not self.cinema_url.endswith("/buytickets/" + self.venue_id):
            raise ValueError("cinema URL must end with buytickets/venue ID")
        return self


class DistrictSettings(Model):
    movie_url: str = (
        "https://www.district.in/movies/avengers-doomsday-movie-tickets-MV176735"
    )
    cinema_url: str = "https://www.district.in/movies/cinepolis-bsr-mall-omr-thoraipakkam-chennai-in-chennai-CD9505"
    movie_id: str = Field(default="176735", pattern=r"^[0-9]+$")
    venue_id: str = Field(default="9505", pattern=r"^[0-9]+$")

    @model_validator(mode="after")
    def official_urls(self) -> "DistrictSettings":
        from urllib.parse import urlparse

        for url, suffix in (
            (self.movie_url, "-MV" + self.movie_id),
            (self.cinema_url, "-CD" + self.venue_id),
        ):
            parsed = urlparse(url)
            if (
                parsed.scheme != "https"
                or parsed.netloc != "www.district.in"
                or parsed.query
                or parsed.fragment
                or not parsed.path.startswith("/movies/")
                or not parsed.path.endswith(suffix)
            ):
                raise ValueError(
                    "District URLs must match official host and configured IDs"
                )
        return self


class Config(Model):
    target: Target
    district: DistrictSettings = Field(default_factory=DistrictSettings)
    bookmyshow: BookMyShowSettings = Field(default_factory=BookMyShowSettings)
    providers: dict[Provider, bool]
    retry: Retry = Field(default_factory=Retry)
    monitor: Monitor = Field(default_factory=Monitor)
    notifications: Notifications = Field(default_factory=Notifications)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @model_validator(mode="after")
    def enabled_provider(self) -> "Config":
        if not any(self.providers.values()):
            raise ValueError("enable at least one provider")
        return self


def load_config(path: Path) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text()))
