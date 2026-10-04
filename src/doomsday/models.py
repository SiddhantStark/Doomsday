"""Shared validated contracts; provider integrations are added in later phases."""

from datetime import date, time
from enum import StrEnum

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Provider(StrEnum):
    BOOKMYSHOW = "bookmyshow"
    DISTRICT = "district"


class ShowStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    FAST_FILLING = "FAST_FILLING"
    SOLD_OUT = "SOLD_OUT"
    COMING_SOON = "COMING_SOON"
    NOT_BOOKABLE = "NOT_BOOKABLE"
    UNKNOWN = "UNKNOWN"


class MonitorState(StrEnum):
    MOVIE_NOT_LISTED = "MOVIE_NOT_LISTED"
    MOVIE_LISTED = "MOVIE_LISTED"
    COMING_SOON = "COMING_SOON"
    BOOKING_OPEN = "BOOKING_OPEN"
    TARGET_DATE_AVAILABLE = "TARGET_DATE_AVAILABLE"
    TARGET_VENUE_AVAILABLE = "TARGET_VENUE_AVAILABLE"
    FIRST_SHOW_AVAILABLE = "FIRST_SHOW_AVAILABLE"
    CHECK_FAILED = "CHECK_FAILED"


class Show(Model):
    starts_at: AwareDatetime
    status: ShowStatus
    booking_url: HttpUrl | None = None

    @property
    def bookable(self) -> bool:
        return self.status in {ShowStatus.AVAILABLE, ShowStatus.FAST_FILLING}


class ProviderResult(Model):
    provider: Provider
    movie: str = Field(min_length=1)
    city: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    target_date: date
    state: MonitorState
    checked_at: AwareDatetime
    shows: list[Show] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def consistent(self) -> "ProviderResult":
        from .time_utils import IST

        if any(
            show.starts_at.astimezone(IST).date() != self.target_date
            for show in self.shows
        ):
            raise ValueError("show date differs from target date in IST")
        available = any(show.bookable for show in self.shows)
        if available != (self.state == MonitorState.FIRST_SHOW_AVAILABLE):
            raise ValueError("bookable shows require FIRST_SHOW_AVAILABLE state")
        if self.state == MonitorState.CHECK_FAILED and not self.error:
            raise ValueError("CHECK_FAILED requires an error")
        if self.state != MonitorState.CHECK_FAILED and self.error:
            raise ValueError("error requires CHECK_FAILED")
        return self

    @property
    def earliest_show(self) -> Show | None:
        return min(
            (show for show in self.shows if show.bookable),
            key=lambda show: show.starts_at,
            default=None,
        )


class EventKind(StrEnum):
    STATUS_SUMMARY = "STATUS_SUMMARY"
    BOOKING_OPENED = "BOOKING_OPENED"
    EARLIER_SHOW_ADDED = "EARLIER_SHOW_ADDED"
    AVAILABILITY_REAPPEARED = "AVAILABILITY_REAPPEARED"
    HEALTH_WARNING = "HEALTH_WARNING"


class NotificationEvent(Model):
    kind: EventKind
    provider: Provider
    target_date: date
    created_at: AwareDatetime
    first_show: time | None = None
    booking_url: HttpUrl | None = None
    preview: bool = True
