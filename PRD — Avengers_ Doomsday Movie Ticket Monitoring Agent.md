# Product Requirements Document (PRD)

## Product Name

**Avengers: Doomsday Ticket Monitoring Agent**

## Version

**v1.3**

Updated: September 28, 2026. Telegram is the only external alert channel. The project must operate without paid services.

Implementation checklist: [Development Roadmap](ROADMAP.md).

Phase 0 evidence: [Provider feasibility](docs/PHASE_0_FEASIBILITY.md) and [Telegram setup](docs/TELEGRAM_SETUP.md).

## Target Release

Initial development: September–October 2026  
Monitoring activation: November 2026  
Primary target event: **Avengers: Doomsday — December 18, 2026**

---

# 1. Product Overview

The Avengers: Doomsday Ticket Monitoring Agent is an automated system that monitors online movie-ticket platforms for ticket availability for a specific movie, cinema, date, and show.

The initial target is:

- Movie: **Avengers: Doomsday**
- City: **Chennai**
- Venue: **BSR Mall / BSR Cinemas, Thoraipakkam**
- Target date: **December 18, 2026**
- Target show: **Earliest available show of the day**
- Platforms:
  - BookMyShow
  - District
- Primary notification channel:
  - Telegram
- Operational output:
  - Console / workflow logs

The system should automatically check supported booking platforms at configurable intervals and immediately notify the user when ticket availability changes in a meaningful way.

---

# 2. Problem Statement

Movie tickets for highly anticipated releases can become available without a predictable announcement time.

For major releases such as Avengers: Doomsday, desirable seats for the first show may sell quickly after bookings open.

Manually checking BookMyShow and District repeatedly is:

- Time-consuming
- Easy to forget
- Inefficient
- Difficult to perform continuously
- Unreliable during working or sleeping hours

The user needs an automated monitoring system capable of detecting when relevant tickets become bookable and sending an immediate notification containing the booking link and earliest available showtime.

---

# 3. Product Goal

Build a reliable automated monitoring agent that:

1. Monitors BookMyShow and District.
2. Searches for Avengers: Doomsday.
3. Checks Chennai.
4. Finds BSR Mall / BSR Cinemas, Thoraipakkam.
5. Checks shows for December 18, 2026.
6. Determines the earliest bookable show.
7. Detects meaningful changes in availability.
8. Sends an alert immediately when tickets become available.
9. Avoids sending duplicate notifications.
10. Continues monitoring automatically without requiring the user's laptop to remain online.

---

# 4. Success Criteria

The product will be considered successful when:

- The monitor runs automatically without manual intervention.
- Both configured ticket platforms can be independently checked.
- The system correctly identifies the configured cinema.
- The system correctly identifies December 18, 2026 shows.
- Available showtimes can be extracted and sorted.
- The earliest show can be identified.
- An alert is sent when booking becomes available.
- Duplicate alerts are prevented.
- An alert is sent if a new, earlier show is subsequently added.
- Failures are clearly distinguished from "tickets unavailable."
- Monitoring continues even while the user's personal computer is offline.

---

# 5. Non-Goals

Version 1 will **not**:

- Automatically purchase tickets.
- Automatically select seats.
- Automatically complete payment.
- Store payment information.
- Bypass CAPTCHAs.
- Circumvent platform security mechanisms.
- Attempt to defeat bot-detection systems.
- Create multiple booking accounts.
- Reserve tickets.
- Scrape unrelated movies or cinemas.
- Provide ticket resale functionality.

The system only monitors availability and sends notifications.

The user completes the actual booking manually.

---

# 6. Primary User

## User Persona

Movie enthusiast who wants to attend the earliest possible screening of a highly anticipated movie.

### User need

> "I want to know immediately when tickets for Avengers: Doomsday become available at BSR Thoraipakkam for December 18, 2026, without repeatedly checking BookMyShow and District myself."

---

# 7. Core User Story

> As a moviegoer, I want an automated system to monitor BookMyShow and District for Avengers: Doomsday tickets at BSR Thoraipakkam on December 18, 2026 so that I can receive an alert as soon as the earliest show becomes bookable.

---

# 8. Secondary User Stories

### Ticket availability

> As a user, I want to know when tickets become bookable so that I can immediately open the booking platform.

### Earliest show detection

> As a user, I want the system to identify the earliest show automatically rather than relying on a predefined showtime.

### New earlier show

> As a user, I want another notification if an earlier show is added after bookings have already opened.

### Multiple platforms

> As a user, I want BookMyShow and District monitored independently so that availability on either platform triggers an alert.

### Reliability

> As a user, I want errors to be reported separately from unavailable tickets so that a broken monitor does not create false confidence.

---

# 9. Functional Requirements

## FR-1: Scheduled Monitoring

The system must run automatically at configurable intervals.

Default:

```text
60 minutes
```

Example:

```text
12:17
13:17
14:17
15:17
```

The monitoring interval must be configurable.

Possible future intervals:

```text
Daily
6 hours
1 hour
```

---

# 10. Monitoring Strategy

The system should support different monitoring frequencies depending on proximity to release.

Recommended configuration:

### September–October

```text
1 check/day
```

### November

```text
Every 6 hours
```

### December 1–10

```text
Every 1 hour
```

### December 11 until booking opens

```text
Every 60 minutes
```

Monitoring frequency should be configurable rather than hard-coded.

---

# 11. Supported Ticket Providers

Version 1 must support:

## BookMyShow

The system must attempt to determine:

- Whether the movie exists.
- Whether bookings are open.
- Whether December 18 is selectable.
- Whether BSR Thoraipakkam exists in the cinema list.
- Available showtimes.
- Booking status of each show.
- Direct booking URL where possible.

## District

The system must perform equivalent monitoring for District.

Each provider must operate independently.

Failure of one provider must not prevent checking the other.

---

# 12. Provider Architecture

Each booking provider should implement a common abstraction.

Example conceptual interface:

```python
class TicketProvider:
    def check_availability(movie, city, venue, date):
        pass
```

Implementations:

```text
BookMyShowProvider
DistrictProvider
```

Future providers could include:

```text
PVR
INOX
Cinepolis
other supported booking platforms
```

without modifying the core monitoring logic.

---

# 13. Configuration

The monitoring target must be stored in configuration.

Example:

```yaml
movie:
  name: "Avengers: Doomsday"

location:
  city: "Chennai"

venue:
  name: "BSR Mall Thoraipakkam"

target:
  date: "2026-12-18"
  show_strategy: "EARLIEST_AVAILABLE"

monitor:
  interval_minutes: 60
```

Secrets must not be stored in this configuration.

---

# 14. Venue Matching

Venue names may differ between providers.

Examples could include:

```text
BSR Mall Thoraipakkam
BSR Cinemas Thoraipakkam
BSR Mall, OMR
BSR Mall: Thoraipakkam
```

The system must support configurable aliases.

Example:

```python
VENUE_ALIASES = [
    "BSR Mall Thoraipakkam",
    "BSR Cinemas Thoraipakkam",
    "BSR Mall: Thoraipakkam",
]
```

Matching should preferably be case-insensitive and normalized.

The system should avoid extremely loose matching that could accidentally select another cinema.

---

# 15. Date Detection

The system must specifically inspect:

```text
December 18, 2026
```

Availability on another date must not trigger the primary alert.

For example:

```text
December 17 → ignore
December 18 → monitor
December 19 → ignore
```

unless additional target dates are explicitly configured later.

---

# 16. Showtime Extraction

Once the target cinema is found, the monitor should extract all available showtimes.

Example:

```text
07:00
09:30
12:45
16:00
20:30
```

The system must convert them into comparable time values.

The earliest available show should then be selected.

Example:

```text
Shows:
07:00
09:30
12:45

Earliest:
07:00
```

The earliest show must **not** be hard-coded.

---

# 17. Availability Detection

Each show should preferably include a normalized status.

Possible values:

```text
AVAILABLE
SOLD_OUT
FAST_FILLING
COMING_SOON
NOT_BOOKABLE
UNKNOWN
```

The exact provider labels may differ.

The system converts provider-specific statuses into internal normalized statuses.

---

# 18. System State Model

The system should model the monitoring lifecycle using explicit states.

Recommended states:

```text
MOVIE_NOT_LISTED

MOVIE_LISTED

COMING_SOON

BOOKING_OPEN

TARGET_DATE_AVAILABLE

TARGET_VENUE_AVAILABLE

FIRST_SHOW_AVAILABLE

CHECK_FAILED
```

A provider must always return a meaningful state.

---

# 19. Important State Transitions

The most important transition is:

```text
NOT_AVAILABLE
        ↓
AVAILABLE
```

Example:

Previous run:

```text
BookMyShow:
COMING_SOON
```

Current run:

```text
BookMyShow:
FIRST_SHOW_AVAILABLE
```

Action:

```text
SEND ALERT
```

---

# 20. Duplicate Alert Prevention

The monitor must not send the same notification on every scheduled run.

Example:

```text
14:00
NOT_AVAILABLE

14:30
AVAILABLE
→ ALERT

15:00
AVAILABLE
→ NO ALERT

15:30
AVAILABLE
→ NO ALERT
```

The system must persist enough state to know whether the user has already been notified.

---

# 21. Earlier-Show Detection

The agent must detect if an earlier show appears after the first availability notification.

Example:

Initial state:

```text
First show:
10:30 AM
```

Later:

```text
First show:
07:00 AM
```

This transition should trigger a new alert.

Example:

```text
🚨 EARLIER SHOW DETECTED

Previous earliest show:
10:30 AM

New earliest show:
07:00 AM
```

---

# 22. Multiple Platform Behavior

Each platform should maintain its own state.

Example:

```text
BookMyShow:
AVAILABLE

District:
COMING_SOON
```

BookMyShow availability should immediately trigger an alert.

The system should not wait for both providers to report availability.

---

# 23. Result Data Model

Every provider should convert its result into a common structure.

Example:

```json
{
  "platform": "BookMyShow",
  "movie": "Avengers: Doomsday",
  "city": "Chennai",
  "venue": "BSR Mall Thoraipakkam",
  "date": "2026-12-18",
  "status": "FIRST_SHOW_AVAILABLE",
  "available": true,
  "showtimes": [
    "09:30",
    "13:00",
    "16:45"
  ],
  "first_show": "09:30",
  "booking_url": "https://...",
  "checked_at": "2026-12-05T14:30:00+05:30"
}
```

This abstraction prevents provider-specific logic from spreading throughout the application.

---

# 24. Notification Requirements

## Primary Channel

Telegram.

## Development Channel

Console / GitHub Actions logs.

Each notification channel should be modular.

Example:

```text
NotificationService

├── TelegramNotifier
└── ConsoleNotifier
```

---

## Telegram Implementation Requirements

- Use the standard Telegram Bot API with `TelegramNotifier` for availability, earlier-show, and throttled health alerts.
- Create the bot through @BotFather. The recipient must start a private chat with the bot before it can send alerts.
- Store `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` only in local `.env` or deployment secrets. Redact tokens, token-bearing request URLs, and private chat identifiers from logs.
- Send plain text with booking links initially. No business verification or approved message templates are required for this standard bot flow.
- Persist notification events before sending. Track pending, accepted, failed, or uncertain status, attempt count, and last sanitized error. Handle returned `message_id` privately; do not persist it in public state.
- Mark an event accepted only after a successful Bot API response. This is not proof of a phone notification or a human read; do not build delivery/read-receipt polling.
- Retry transient errors with bounded backoff and respect `retry_after` for rate limits. Invalid credentials or a blocked bot require operator action, not endless retries.
- An ambiguous network timeout may occur after Telegram accepted a message. Record uncertainty; exactly-once delivery cannot be guaranteed across that failure.
- Failed sends remain visible in logs and persistent state. Telegram is the only external alert channel; there is no secondary messaging fallback.
- Dry-run mode must not send messages or advance production notification state.
- Keep paid broadcasts disabled and stay within free API limits. Hosting, storage, and diagnostic retention must also remain within verified free allowances. If a free limit is reached, stop or reduce operation and log the issue rather than enable billing automatically.

References: [Telegram bots](https://core.telegram.org/bots), [Bot API](https://core.telegram.org/bots/api), and [limits](https://core.telegram.org/bots/faq).

---

# 25. Ticket Availability Notification

Example message:

```text
🚨 AVENGERS: DOOMSDAY TICKET ALERT

🎬 Avengers: Doomsday
📅 December 18, 2026
📍 BSR Mall, Thoraipakkam

🎟 Platform:
BookMyShow

🕘 Earliest Show:
9:30 AM

✅ Booking Status:
OPEN

🔥 Tickets were just detected.

BOOK NOW:
<booking-link>

Checked:
05 Dec 2026 • 2:30 PM IST
```

The booking URL must be included whenever available.

---

# 26. Earlier-Show Notification

Example:

```text
🚨 NEW EARLIER SHOW DETECTED

🎬 Avengers: Doomsday
📍 BSR Mall, Thoraipakkam
📅 December 18, 2026

Previous first show:
10:30 AM

New first show:
7:00 AM

Platform:
BookMyShow

BOOK NOW:
<booking-link>
```

---

# 27. Error Notifications

Ordinary temporary errors should primarily be logged.

The user should not receive a Telegram message for every temporary timeout.

Possible strategy:

```text
1 failure
→ Log only

2 consecutive failures
→ Log

3+ consecutive failures
→ Send health alert
```

Example:

```text
⚠️ TICKET MONITOR WARNING

BookMyShow monitoring has failed
3 consecutive times.

Last error:
Timeout waiting for cinema list.

District monitoring is still operational.
```

---

# 28. Scraping Strategy

The implementation should use a layered strategy.

## Preferred approach

### Level 1 — HTTP/API

Attempt to retrieve publicly accessible data using:

```text
HTTP requests
JSON endpoints
HTML parsing
```

Advantages:

- Lightweight
- Faster
- Lower resource usage
- Better suited for scheduled server execution

---

# 29. Browser Automation Fallback

When HTTP monitoring is insufficient, use:

```text
Playwright
```

with headless Chromium.

Possible actions:

```text
Open website

Select Chennai

Find Avengers: Doomsday

Choose December 18

Find BSR Thoraipakkam

Read showtimes

Determine booking availability
```

Browser automation should only be used where required.

---

# 30. Automation Safety

The system must not:

- Solve or bypass CAPTCHAs.
- Attempt to defeat anti-bot mechanisms.
- Circumvent authentication restrictions.
- Generate abnormal traffic.
- Attempt to imitate multiple users.

If a provider blocks automated access:

```text
status = CHECK_FAILED
```

and the system should gracefully continue with other supported providers.

---

# 31. Deployment Strategy

## Primary Deployment

GitHub Actions.

Benefits:

- No permanent server required.
- No laptop required.
- Scheduled execution.
- Simple secret management.
- Logs retained for debugging.
- Suitable for periodic monitoring.

---

# 32. GitHub Actions Workflow

The workflow should:

```text
Trigger on schedule

↓ 

Checkout repository

↓

Install Python

↓

Install dependencies

↓

Install Playwright browser if required

↓

Run ticket monitor

↓

Send notifications when needed

↓

Store/persist state

↓

Finish
```

---

# 33. Scheduling

The schedule should avoid unnecessary exact top-of-hour execution where possible.

Example:

```text
12:17
13:17
14:17
15:17
```

instead of:

```text
12:00
13:00
14:00
15:00
```

The application itself should not assume execution occurs at the exact scheduled second. GitHub Actions schedules can be delayed or dropped under load, so this is best-effort monitoring, not a guaranteed hourly service. Alert immediately after detection; detection latency includes the polling interval and scheduler delays. Record stale checks and evaluate a dedicated scheduler before the release window if measured reliability is insufficient. See [GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

---

# 34. State Persistence

A persistent state is required to compare current results against previous runs.

Example:

```json
{
  "bookmyshow": {
    "status": "COMING_SOON",
    "available": false,
    "first_show": null,
    "last_checked": "2026-11-30T10:00:00+05:30",
    "consecutive_failures": 0
  },

  "district": {
    "status": "COMING_SOON",
    "available": false,
    "first_show": null,
    "last_checked": "2026-11-30T10:00:00+05:30",
    "consecutive_failures": 0
  }
}
```

Possible persistence options:

### V1

```text
JSON state file
```

### Future

```text
SQLite
Redis
PostgreSQL
cloud key-value store
```

---

# 35. Important GitHub Actions Consideration

Because each GitHub Actions execution runs in a fresh environment, state cannot simply remain as a local file between independent runs unless explicitly persisted.

Use a small JSON state file on a dedicated `monitor-state` branch in the public repository. Standard Linux GitHub Actions runners execute hourly near release, with occasional delays accepted. No additional account or paid database is required. See [hosting/storage decision](docs/HOSTING_STORAGE.md).

Serialize scheduled/manual runs. Persist pending events before sends and accepted markers after success. A failed pre-send push stops notification processing. Missing/corrupt state after initialization must not silently reset history. Public state includes only monitoring facts and logical event status, never bot tokens, chat IDs, private message IDs, or raw API responses. A crash after sending but before saving acceptance can still cause an uncertain outcome; exactly-once messaging is not guaranteed.

---

# 36. Logging Requirements

Each execution must produce structured logs.

Example:

```text
==============================================
AVENGERS TICKET MONITOR
==============================================

Timestamp:
2026-12-05 14:47 IST

Movie:
Avengers: Doomsday

Date:
18 December 2026

Venue:
BSR Mall Thoraipakkam


BOOKMYSHOW
----------------------------------------------

Movie found:
YES

Target date:
YES

Venue found:
YES

Shows:
09:30
13:00
16:45

Earliest show:
09:30

Status:
AVAILABLE


DISTRICT
----------------------------------------------

Movie found:
YES

Target date:
YES

Venue found:
NO

Status:
COMING_SOON


CHANGE DETECTION
----------------------------------------------

BookMyShow:
COMING_SOON → AVAILABLE

Action:
SEND TELEGRAM ALERT


RESULT
----------------------------------------------

Monitor completed successfully.
```

---

# 37. Error Handling

The system must distinguish between:

```text
NO_TICKETS
```

and:

```text
CHECK_FAILED
```

Example:

```text
HTTP timeout
```

must not be interpreted as:

```text
Tickets unavailable
```

Instead:

```text
BookMyShow:
CHECK_FAILED

District:
AVAILABLE
```

The remaining providers should still execute.

---

# 38. Retry Strategy

Temporary failures should support retries.

Recommended:

```text
Attempt 1
↓ failure

Wait 5 seconds

Attempt 2
↓ failure

Wait 15 seconds

Attempt 3
↓ failure

Mark CHECK_FAILED
```

Retry values should be configurable.

---

# 39. Observability

The system should capture:

- Provider status.
- Last successful check.
- Last failure.
- Number of consecutive failures.
- Number of available shows.
- Current first show.
- Whether an alert was sent.
- Check duration.

Optional future metrics:

```text
Checks performed
Provider success rate
Average response time
Ticket availability detection timestamp
```

---

# 40. Debugging Support

When browser automation fails, development/debug mode should optionally save:

```text
Screenshot
HTML snapshot
Browser logs
Error stack trace
```

These should **not** be sent to Telegram by default.

---

# 41. Secrets Management

Sensitive values must never be committed to Git.

Examples:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Locally:

```text
.env
```

GitHub:

```text
GitHub Actions Secrets
```

`.env` must be included in `.gitignore`.

---

# 42. Suggested Technology Stack

## Language

```text
Python 3.12+
```

## Project Management

Use uv with `pyproject.toml`, a committed `uv.lock`, and `.python-version`. Install with `uv sync --locked`; execute commands with `uv run --locked`. Development tools use the `dev` dependency group; deployment excludes it with `--no-dev`.

## HTTP

```text
httpx
```

or:

```text
requests
```

## HTML Parsing

```text
BeautifulSoup
```

when applicable.

## Browser Automation

```text
Playwright
```

## Configuration

```text
PyYAML
python-dotenv
```

## Notifications

```text
Telegram Bot API
```

## Testing

```text
pytest
```

## Deployment

```text
GitHub Actions
```

## Packaging

```text
Docker
```

---

# 43. Suggested Repository Structure

```text
avengers-ticket-monitor/
│
├── src/
│   │
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   │
│   ├── providers/
│   │   ├── base.py
│   │   ├── bookmyshow.py
│   │   └── district.py
│   │
│   ├── services/
│   │   ├── monitoring_service.py
│   │   └── showtime_service.py
│   │
│   ├── notifications/
│   │   ├── base.py
│   │   ├── telegram.py
│   │   └── console.py
│   │
│   ├── state/
│   │   ├── state_manager.py
│   │   └── state.json
│   │
│   └── utils/
│       ├── logger.py
│       ├── time.py
│       └── normalization.py
│
├── tests/
│   ├── test_bookmyshow.py
│   ├── test_district.py
│   ├── test_state_manager.py
│   └── test_showtime_service.py
│
├── .github/
│   └── workflows/
│       └── monitor.yml
│
├── config/
│   └── monitor.yml
│
├── Dockerfile
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example
├── .gitignore
├── setup.sh
└── README.md
```

---

# 44. Core Application Flow

```text
START

↓

Load configuration

↓

Load previous monitoring state

↓

Initialize providers

↓

Check BookMyShow

↓

Normalize result

↓

Check District

↓

Normalize result

↓

Combine provider results

↓

Determine earliest show per provider

↓

Compare with previous state

↓

Meaningful change?
        │
     ┌──┴──┐
     │     │
    NO    YES
     │     │
     │     ↓
     │   Send Telegram
     │
     ↓
Update state

↓

Write logs

↓

END
```

---

# 45. Meaningful Change Definition

The following should trigger notifications.

## Event 1

Tickets become available.

```text
false → true
```

---

## Event 2

An earlier show appears.

```text
10:30 → 07:00
```

---

## Event 3

A second provider becomes available.

Example:

```text
BookMyShow:
Already available

District:
Not available → available
```

Optionally notify the user with the second booking link.

---

## Event 4

Tickets disappear and later reappear.

Example:

```text
AVAILABLE
↓
NOT_AVAILABLE
↓
AVAILABLE
```

The second availability should trigger a new alert.

---

# 46. Events That Should NOT Trigger Alerts

Examples:

```text
AVAILABLE → AVAILABLE
```

No change.

```text
COMING_SOON → COMING_SOON
```

No change.

```text
10:30 first show → 10:30 first show
```

No change.

A temporary network error should also not produce a ticket alert.

---

# 47. Configuration Example

```yaml
movie:
  name: "Avengers: Doomsday"

city:
  name: "Chennai"

venue:
  canonical_name: "BSR Mall Thoraipakkam"

  aliases:
    - "BSR Mall Thoraipakkam"
    - "BSR Cinemas Thoraipakkam"
    - "BSR Mall: Thoraipakkam"
    - "Cinepolis: BSR Mall, OMR, Thoraipakkam"
    - "Cinepolis BSR Mall OMR"

target:
  date: "2026-12-18"
  show_strategy: "EARLIEST_AVAILABLE"

providers:
  bookmyshow:
    enabled: true

  district:
    enabled: true

notifications:
  telegram:
    enabled: true
    allow_paid_broadcast: false

monitor:
  interval_minutes: 60

retry:
  attempts: 3

logging:
  level: "INFO"
```

---

# 48. Environment Variables

Example:

```text
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

No real credentials should appear in `.env.example`.

---

# 49. Testing Requirements

The system should include unit tests for:

### Showtime sorting

Input:

```text
10:30
07:00
13:00
```

Expected:

```text
07:00
```

---

### Venue normalization

Input:

```text
BSR Mall: Thoraipakkam
```

Expected match:

```text
BSR Mall Thoraipakkam
```

---

### New availability

Previous:

```text
available = false
```

Current:

```text
available = true
```

Expected:

```text
send_notification = true
```

---

### Duplicate availability

Previous:

```text
available = true
first_show = 09:30
```

Current:

```text
available = true
first_show = 09:30
```

Expected:

```text
send_notification = false
```

---

### Earlier show

Previous:

```text
first_show = 10:30
```

Current:

```text
first_show = 07:00
```

Expected:

```text
send_notification = true
```

---

### Provider failure

BookMyShow:

```text
CHECK_FAILED
```

District:

```text
AVAILABLE
```

Expected:

```text
District result still processed
```

---

# 50. Acceptance Criteria

## AC-1

Given tickets are unavailable,

when the monitor checks the platform,

then no ticket notification should be sent.

---

## AC-2

Given tickets become available,

when the next monitoring execution runs,

then a Telegram message should be submitted and a successful API response and message ID recorded.

---

## AC-3

Given tickets remain available,

when another execution runs,

then no duplicate notification should be sent.

---

## AC-4

Given 10:30 AM was previously the earliest show,

when a 7:00 AM show becomes available,

then the user should receive another notification.

---

## AC-5

Given BookMyShow fails,

when District successfully returns ticket availability,

then the District result must still trigger an alert.

---

## AC-6

Given both providers fail,

when the monitor completes,

then the run must be recorded as failed rather than "tickets unavailable."

---

## AC-7

Given multiple shows exist,

when showtimes are processed,

then the chronologically earliest valid bookable show must be selected.

---

## AC-8

Given the recipient previously started the bot and has not blocked it, unattended alerts must work without daily user messages or paid broadcasts.

## AC-9

Given Telegram rejects a send, the event remains failed or pending retry and a sanitized error is logged. An ambiguous timeout is recorded as uncertain, not confirmed success.

## AC-10

Given a fresh cloud runner or an overlapping trigger, durable state and concurrency protection must prevent routine duplicate alerts.

## AC-11

Given a provider check fails between two identical available results, the failure must not create a false reappearance event.

---

# 51. MVP Scope

The MVP should contain:

```text
BookMyShow monitoring

District monitoring

Target venue matching

Target date matching

Showtime extraction

Earliest-show detection

State management

Telegram alerts

Console logging

GitHub Actions scheduling

Environment-based secrets

Error handling

Retries
```

---

# 52. Post-MVP Features

Possible enhancements after the initial version:

### Monitoring dashboard

Show:

```text
Last check

Platform status

First show

Number of shows

Last alert

Errors
```

---

### Multiple cinemas

Example:

```text
BSR Mall

AGS Navalur

PVR ECR

SPI Palazzo
```

---

### Multiple cities

Example:

```text
Chennai

Bengaluru

Mumbai
```

---

### Multiple movies

Generic configuration:

```text
movies:
  - Avengers: Doomsday
  - Movie B
  - Movie C
```

---

### Seat monitoring

Future versions could monitor:

```text
seat availability counts
```

where technically and operationally practical.

---

### Preferred seating

Potential future configuration:

```text
Recliner

IMAX

4DX

Premium

Middle rows
```

without automatically booking seats.

---

### Web dashboard

Possible stack:

```text
React

FastAPI

PostgreSQL
```

Display live monitoring history.

---

# 53. Future Agent Architecture

The project can eventually evolve from:

```text
Movie-specific monitor
```

into:

```text
Generic Ticket Monitoring Platform
```

Architecture:

```text
                  Monitoring Engine

                        │
          ┌─────────────┼─────────────┐
          │             │             │

      Movie Agent   Concert Agent   Event Agent

          │
          ▼

        Providers

          │

   ┌──────┼─────────┐
   │      │         │

 BMS   District   Others

          │
          ▼

    Change Detection

          │
          ▼

      Notification

          │
          ▼

       Telegram
```

---

# 54. Development Phases

The detailed checklist, dependencies, estimates, and exit criteria live in [ROADMAP.md](ROADMAP.md).

| Phase | Outcome | Estimated engineering effort |
|---|---|---|
| 0 — Feasibility and onboarding | Validate provider access; create Telegram bot and start private chat | 1–2 days |
| 1 — Foundation | Typed models, validated configuration, CLI, logging, fixture-driven dry run | 1 day |
| 2 — BookMyShow | First provider with verified extraction and failure handling | 2–3 days |
| 3 — District | Independent second provider using the same result contract | 2–3 days |
| 4 — State and events | Durable state, duplicate prevention, earlier-show and reappearance detection | 1–2 days |
| 5 — Telegram alerts | Message formatting, API acceptance tracking, retries, failure handling | 1 day |
| 6 — Deployment | Scheduled cloud execution, durable state restoration, secrets, concurrency control | 1–2 days |
| 7 — Readiness | End-to-end verification, soak test, operating runbook | 2–3 days plus observation time |
| 8 — Optional portability | Docker packaging and alternate scheduler if needed | 1 day |

Estimates are planning ranges, not guarantees. Provider-access blockers may add time. Begin onboarding in Phase 0 while local development proceeds. Do not count fixture-based parsing as proof that live platform monitoring works.

---

# 55. Definition of Done

Version 1 is complete when the following scenario works end-to-end:

```text
GitHub Actions starts automatically

↓

Monitor checks BookMyShow

↓

Monitor checks District

↓

Avengers: Doomsday is found

↓

December 18 is selected

↓

BSR Thoraipakkam is found

↓

Available showtimes are extracted

↓

Earliest show is calculated

↓

Previous state = unavailable

Current state = available

↓

Telegram notification sent

↓

Booking URL included

↓

State updated

↓

Next scheduled run executes

↓

Same state detected

↓

No duplicate notification
```

---

# 56. Primary Product Principle

The monitor should optimize for:

> **Reliable detection of meaningful ticket-availability changes rather than aggressive webpage scraping.**

The goal is not to check pages as frequently as technically possible.

The goal is to reliably detect:

```text
Tickets became available
```

or:

```text
A better/earlier show became available
```

and immediately inform the user.

---

# 57. Final Product Requirement

The core requirement of the project can be summarized as:

> Automatically monitor BookMyShow and District for Avengers: Doomsday tickets at BSR Mall Thoraipakkam in Chennai for December 18, 2026. When tickets become bookable, immediately notify the user through Telegram with the earliest available showtime and booking link. Continue monitoring for meaningful changes such as the addition of an earlier show while avoiding duplicate notifications and clearly distinguishing platform failures from unavailable tickets.