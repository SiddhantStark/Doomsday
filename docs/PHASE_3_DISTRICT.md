# Phase 3 — District

Implemented September 28, 2026. District uses public HTML with `__NEXT_DATA__`; no account, private endpoint, or browser is required. HTTPS verification uses the operating system certificate store through truststore.

## Validation

- Live Avengers: Doomsday movie and December 18 venue requests succeeded. Venue identity matched Cinepolis BSR Mall OMR, Thoraipakkam, Chennai. The date-specific response had an empty session list and explicit “No shows playing at the moment” text. Result: `MOVIE_LISTED`, no shows. This does not claim bookings are open or that the movie is unavailable everywhere.
- An isolated live September 28 check for Heart of the Beast returned a `FAST_FILLING` show at 22:20 IST. The production target was unchanged.
- A combined live invocation returned BookMyShow `CHECK_FAILED / HTTP_403` and District `MOVIE_LISTED` independently. Overall exit code 1 signals partial failure; successful results remain in output.
- No Telegram messages or production state writes occurred.

## Interpretation and safeguards

Match movie content ID and name, cinema ID and venue alias, city, requested date URL and date-specific server-state key. Session identity and converted calendar date must also agree. Missing or malformed data fails closed. An empty future schedule requires both the observed empty schema and explicit no-shows text.

Raw naive District showtimes are UTC: observed 16:50 corresponds to rendered 22:20 IST. Convert before checking the date or comparing shows. Available and Filling Fast are bookable only with `disableClick=false` and positive availability. Sold Out, disabled, zero availability, and unknown statuses cannot trigger availability. Booking links lead to the selected venue/date page, without starting checkout.

Fixtures are reduced public responses captured September 28; tests mutate copies for synthetic failures and edge cases. They contain no credentials or user data. Show data changes throughout the day, so fixture results are not current availability claims.

## Commands

```sh
uv run --locked doomsday --once --dry-run --provider district
uv run --locked doomsday --once --dry-run --provider all
```

`all` runs enabled providers. BookMyShow still needs its separately installed Chromium browser. District-only execution does not launch a browser. Exit codes: 0 successful checks, 1 any provider failed, 2 invalid configuration or arguments.

Remaining work: durable state/change detection (Phase 4), automated alerts (Phase 5), and cloud access validation (Phase 6). District's observed schema is not a stable API contract; parser changes may be needed. BookMyShow live acceptance remains blocked.
