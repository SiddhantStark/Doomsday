# Multiple cinema locations

Enabled November 7, 2026 at the user's request. The Mac LaunchAgent reads `config/locations.yml`, containing independent per-location configurations:

- `monitor.yml`: BSR Mall Thoraipakkam, Chennai (existing configuration/history retained).
- `monitor-mumbai.yml`: Miraj Cinemas: IMAX, Wadala, Mumbai.

Both target Avengers: Doomsday on December 18, 2026, choosing the earliest bookable show on each enabled provider. The shared local state already keys observations by provider/movie/city/venue/date, so no reset or schema migration was necessary. One combined provider summary is sent per cinema when that cinema is checked; each message names the cinema and city. Availability-change alerts also identify their location. All messages use the configured Telegram group.

Each configuration retains its own cadence: currently six-hourly in November and hourly in December, subject to awake/online Mac and LaunchAgent timing. The scheduler validates the whole manifest before checks, skips locations that are not due, continues after an individual provider failure, and halts on shared state errors. The whole-run lock covers both locations. One provider/location failing is not a negative availability result for the other.

The supplied BookMyShow date suffix is replaced with the configured target date at runtime. District's search tracking parameter was removed; the venue ID is 1038682. Public page verification matched the cinema ID/name and explicit Mumbai address. This District URL leaves its city label empty, so the parser accepts an exact comma-delimited city component from the cinema address only when the label is absent. A conflicting nonempty city label still fails.

## Commands

```sh
# Mumbai-only read-only check:
uv run --locked doomsday --config config/monitor-mumbai.yml --provider all --headed --dry-run
# Read-only state health for every configured location:
uv run --locked python -m doomsday.health
# Cadence-aware multi-location run (sends due summaries/alerts):
uv run --locked python -m doomsday.scheduled --locations config/locations.yml --state .monitor/state.json --headed --notify
```

For normal operation use the LaunchAgent; avoid running a manual writable command concurrently. `--config` single-location CLI behavior remains supported. GitHub scheduling stays disabled and its workflow has not been enabled or validated for this manifest. Do not enable it without revisiting cloud access and migrating current local state.

Tests cover independent state/cadence, separate message contents, continuation after a provider failure and strict address fallback. Both Mumbai provider checks passed live on November 7: COMING_SOON on BookMyShow, MOVIE_LISTED on District. Current venue pages were accessible; future December show and format coverage remains dependent on listings becoming available. A venue name containing IMAX does not imply an IMAX-only filter: the existing strategy considers supported bookable shows at that venue.

Activation evidence: the actual LaunchAgent processed the newly due Mumbai target on November 7 at 21:57 IST, saved both successful results and obtained Telegram acceptance for its group summary. Investigation also found that Chennai District had moved to `cinepolis-bsr-mall-omr-thoraipakkam-chennai-CD9505`; the ID, name and Mumbai/Chennai address separation were verified, and the Chennai config was updated to its canonical URL. A subsequent Chennai check at 21:58 IST succeeded on both providers and its group summary was accepted. One pre-existing November 1 Chennai summary remains uncertain (`TRANSPORT_OUTCOME_UNKNOWN`); it was not replayed or marked accepted. Delivery filtering now scopes even unresolved-event reporting to the selected location. The full suite passes 112 tests.
