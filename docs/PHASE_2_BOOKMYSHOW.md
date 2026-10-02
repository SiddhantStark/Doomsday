# Phase 2 — BookMyShow implementation and validation

Status: implementation tested and local visible-browser movie/venue extraction validated. Default headless and cloud access remain blocked; full live acceptance coverage is still pending.

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

## September 29 — Local visible/headless comparison

Fresh unauthenticated contexts on the same Mac, same Playwright installation (Chromium 153.0.8010.12), `en-IN` locale, IST timezone, and navigation/render waits were used. No reused cookies, stealth settings, or production state writes.

| Page | Visible Chromium | Default headless Chromium |
|---|---|---|
| Avengers: Doomsday, Bengaluru | HTTP 200, movie content | HTTP 403, Cloudflare block |
| Avengers: Doomsday, Chennai | HTTP 200, movie content | HTTP 403, Cloudflare block |
| The Paradise, Bengaluru, September 29 show listings | HTTP 200, cinemas/showtimes visible | HTTP 403, Cloudflare block |
| Cinepolis BSR Mall, Chennai, September 29 schedule | HTTP 200, 25 Book controls | HTTP 403, Cloudflare block |

The existing movie parser returned `COMING_SOON` for Chennai. The existing venue parser processed the captured visible-browser schedule for the isolated current movie Heart of the Beast (ET00504928), returning bookable 16:55 and 22:20 IST shows and selecting 16:55 as earliest. The production Avengers target remained unchanged. The Bengaluru movie-centric schedule has a different DOM and was checked for access/content only, not passed through the cinema-centric parser.

This establishes local visible-browser access and one current-movie parser example. It narrows the previous local failure to differences associated with the launch mode/default browser build; Playwright's default headless launch may use its separate headless-shell executable. It does not identify Cloudflare's exact rule or isolate executable differences from all timing effects. Visible requests were performed first, then headless requests, one per URL, without retries on blocks.

The prior blanket statement that standalone Playwright cannot access BookMyShow is superseded by this evidence. Full language/format coverage, sold-out markup, sustained reliability, and cloud visible-browser access remain unverified. GitHub scheduling remains disabled. No Telegram messages were sent.

### Application integration

The CLI now supports `--headed` for BookMyShow and combined provider checks. Headless remains the default. On September 29, the real CLI completed both configured providers successfully in read-only mode. A separate temporary current-movie config also completed the full BookMyShow movie-page → venue-page → normalized earliest-show flow, returning Heart of the Beast at 16:55 and 22:20 IST. This used the production parser and transport with visible mode; no fixture responses were substituted. The configured Avengers target, notification state, and cloud schedule were unchanged. All 97 tests and Ruff checks passed.
