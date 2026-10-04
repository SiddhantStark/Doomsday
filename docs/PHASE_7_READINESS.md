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

The end-to-end readiness simulation uses a temporary isolated file and an injected fake Telegram transport. It exercises real change detection, event persistence, message formatting, claim/acceptance tracking and restart deduplication. It does not send fabricated availability to the real chat, and it does not modify the production state file. Actual Telegram delivery was previously user-confirmed in Phase 5. The user authorized one additional Phase 7 test message. Telegram accepted it on October 2; recipient receipt was confirmed by the user’s October 4 screenshot. This real send was clearly labeled TEST and did not alter production state; it is separate from the simulated event sequence.

The active LaunchAgent was inspected: loaded and idle between checks, last real provider check at 18:37 IST with BookMyShow COMING_SOON and District MOVIE_LISTED, zero failure counters, no queued events. The second launch at 18:38 IST skipped as not due. Runtime logs now include launcher completion timestamps for reviewing the observation period. [Runbook](RUNBOOK.md) documents credentials, failures, state recovery, uncertain messages, pause/resume, sleep/network gaps, host migration and costs.

## Still open

- Complete and review 48–72 hours of actual Mac operation (October 4–5 at 18:37 IST). This elapsed-time gate cannot be completed immediately. At the daily cadence it provides only a few actual provider checks, not an hourly provider soak test.
- Review sleep/network interruptions, scheduling gaps, parser errors, state consistency and notification duplicates. Extend observation if necessary.
- Revalidate live pages and Telegram before November/December cadence increases.
- Verify future target-date booking, language/format coverage, sold-out layouts, and complete schedule extraction when those listings are available. Historical/current-movie examples do not establish future target coverage.
- Cloud access remains a deferred limitation, not a healthy provider result.

No production availability alert was sent during the automated readiness tests. Phase 7 remains open until the observation and remaining acceptance gates are reviewed.

## Interim observation — October 3, 07:59 IST

Approximately 13 hours 22 minutes have elapsed since the first successful provider run. The LaunchAgent is loaded, has run 15 times, and its most recent completion at 07:41 IST exited 0. Both provider failure counters remain zero; last successful observations are October 2 at 18:37 IST, which is expected under the daily cadence. No unresolved production events are present.

The timestamped launcher log shows roughly hourly completions overnight, with one approximately 1 hour 47 minute gap between 05:53 and 07:41. The cause is not established by these logs; do not assume uninterrupted hourly operation. No provider check was due during that gap, so it has not yet caused a missed daily check. Review subsequent intervals and any known sleep/network interruptions before accepting tighter December timing.

No extra provider checks, test messages, schedule changes, or production-state changes were made for this review. The observation period remains open. Next daily provider check is expected on a launcher wake after roughly October 3 at 18:32 IST (24 hours minus the configured five-minute tolerance); its exact wall-clock launch is best-effort. The 48/72-hour review thresholds remain October 4/5 at 18:37 IST, and completion depends on inspecting actual successful scheduled checks, not elapsed time alone.

## October 4 — Results-summary change

At the user’s request, combined Telegram results summaries are enabled after each actual provider check. Existing change alerts remain active. Schema v3 preserves existing history, and tests cover summary persistence, failed-check wording and restart duplicate suppression. The suite now has 107 passing tests. This feature was added during observation; its automatic scheduled delivery must be observed separately from the initial manual validation.

Live validation at 21:33 IST on October 4: both providers checked successfully; one combined results summary was accepted by Telegram and its accepted marker was verified in local state. No unresolved events remained. This was an explicitly triggered validation check, not an automatic scheduled invocation.
