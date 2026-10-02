# Phase 7 readiness evidence — October 2, 2026

Scope: user-approved temporary Mac host. GitHub access remains blocked and its scheduler remains disabled. No claim of laptop-off operation or complete future-language/format coverage.

## Completed now

105 automated tests pass. Ruff lint and format checks pass. The suite covers:

| Acceptance area | Evidence |
|---|---|
| Movie/date/venue/city guards | BookMyShow and District parser tests plus wrong-target delivery tests |
| Sold-out, disabled and unknown statuses | Provider status tests; unbookable shows cannot establish availability |
| Earliest show and IST conversion | Provider time/date-boundary and earliest-bookable tests |
| First availability, earlier show, disappearance/reappearance | Full state/delivery sequence in `test_readiness.py` |
| Restart deduplication | Fresh store instances after each simulated delivery; exactly three accepted events across the eight-observation sequence |
| Provider failure isolation | Combined provider tests and last-success preservation |
| Delivery rejection/retry/ambiguity | Telegram transport tests: 400/401/403/404, 429, bounded transient retries, timeout, pre/post-send persistence failures and explicit recovery |
| Missing/corrupt state and overlap | State validation, atomic failure and locking tests |
| Target-date stop | Forced scheduled run at midnight December 19 IST makes no provider or delivery call |
| Health visibility | Read-only report checks configured targets, missing observations, staleness, failures and unresolved events |

The end-to-end readiness simulation uses a temporary isolated file and an injected fake Telegram transport. It exercises real change detection, event persistence, message formatting, claim/acceptance tracking and restart deduplication. It does not send fabricated availability to the real chat, and it does not modify the production state file. Actual Telegram delivery was previously user-confirmed in Phase 5. The user authorized one additional Phase 7 test message. Telegram accepted it on October 2; recipient confirmation is pending. This real send was clearly labeled TEST and did not alter production state; it is separate from the simulated event sequence.

The active LaunchAgent was inspected: loaded and idle between checks, last real provider check at 18:37 IST with BookMyShow COMING_SOON and District MOVIE_LISTED, zero failure counters, no queued events. The second launch at 18:38 IST skipped as not due. Runtime logs now include launcher completion timestamps for reviewing the observation period. [Runbook](RUNBOOK.md) documents credentials, failures, state recovery, uncertain messages, pause/resume, sleep/network gaps, host migration and costs.

## Still open

- Complete and review 48–72 hours of actual Mac operation (October 4–5 at 18:37 IST). This elapsed-time gate cannot be completed immediately. At the daily cadence it provides only a few actual provider checks, not an hourly provider soak test.
- Review sleep/network interruptions, scheduling gaps, parser errors, state consistency and notification duplicates. Extend observation if necessary.
- Revalidate live pages and Telegram before November/December cadence increases.
- Verify future target-date booking, language/format coverage, sold-out layouts, and complete schedule extraction when those listings are available. Historical/current-movie examples do not establish future target coverage.
- Cloud access remains a deferred limitation, not a healthy provider result.

No production availability alert was sent during the automated readiness tests. Phase 7 remains open until the observation and remaining acceptance gates are reviewed.
