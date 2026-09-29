# Phase 2 — BookMyShow implementation and validation

Status: implementation and offline tests complete; live acceptance gate blocked by HTTP 403 in standalone Chromium. Do not treat this provider as operational yet.

## Implemented

- Configurable official movie/cinema URLs and provider IDs, validated before access.
- Standard ephemeral Playwright Chromium transport with bounded navigation/render waits, TLS verification, no login, no stealth, and no CAPTCHA bypass.
- Movie title/ID/city validation and explicit coming-soon versus booking-open detection.
- Cinema URL/ID, exact alias, selected day/month/weekday, and full URL calendar date validation.
- Movie-scoped Book controls, 12/24-hour parsing, IST dates, disabled-control exclusion, earliest bookable selection, and durable cinema-page links.
- Read-only CLI with separate fixture/live labels, zero notifications/state writes, and exit code 1 for provider check failure (2 for invalid usage/configuration).
- HTTP/access errors, malformed markup, ambiguous grouping, wrong dates, and transport exceptions produce CHECK_FAILED rather than unavailable tickets.

## Evidence on September 28, 2026

The in-app browser could read the target movie page, which still displayed the interest prompt for upcoming bookings. The BSR schedule page displayed current movie Book buttons; Heart of the Beast had a 22:20 button in the inspected DOM. These observations guided the parser. Reduced HTML fragments are in `tests/fixtures/bookmyshow`; they are manually reduced from inspected DOM, not complete downloaded pages. Edge cases in tests are synthetic modifications.

The actual CLI was run once using the installed standard Chromium build. The public target movie page returned HTTP 403. The CLI returned CHECK_FAILED / HTTP_403, exit code 1, zero messages, and no state changes. The in-app browser success does not establish success for the standalone runtime. No bypass or cookie transfer was attempted.

## Remaining live acceptance checks

- Validate normal standalone access from an allowed runtime before enabling scheduled monitoring. Stop on blocks; request supported access or leave the provider disabled if unavailable.
- When accessible, run the parser against a complete current schedule and compare all extracted shows with the page, including lazy-loaded content. Do not rely on partial virtualized listings to establish the earliest show.
- Verify target December 18 selections and each language/format's movie IDs when listings appear. The current exact-ID configuration does not automatically discover alternate language/format IDs; do not claim comprehensive cross-format coverage until these are verified and configured.
- Validate genuine sold-out markup. Currently disabled Book controls map conservatively to NOT_BOOKABLE; color-only status differences are not interpreted. Missing controls fail closed.
- A missing movie heading or HTTP 404 is ambiguous and remains CHECK_FAILED; the implementation does not claim MOVIE_NOT_LISTED from transport failure.
- Retry orchestration and persistent change detection belong to later reliability/state phases. Current live checks make no automatic retry on 403.

## Commands

```sh
uv sync --locked
uv run --locked playwright install chromium
uv run --locked doomsday --once --dry-run --provider bookmyshow
```

This validation session installed Chromium under `/tmp/doomsday-playwright`. To reuse it locally, prefix the run command with `PLAYWRIGHT_BROWSERS_PATH=/tmp/doomsday-playwright`. The standard install command above uses Playwright's default cache instead.
