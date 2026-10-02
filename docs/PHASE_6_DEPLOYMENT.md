# Phase 6 — GitHub Actions deployment

Repository: https://github.com/SiddhantStark/Doomsday

The source is now its own Git repository, separate from the unrelated Desktop repository. The public repository contains source, sanitized fixtures, documentation, and a lockfile; configured secret values were checked before publication. `.env` remains local. Telegram credentials are stored as repository Actions Secrets.

## Workflows

- `Tests`: locked uv dependencies, Ruff lint/format, and pytest on main pushes and pull requests. Read-only permissions; no Telegram secrets.
- `Ticket monitor`: manual runs plus an hourly wakeup at minute 17 UTC during September–December. All runs use concurrency group `doomsday-monitor` with cancellation disabled. Only default-branch code runs with write permission. No pull-request trigger.
- Scheduled monitoring requires repository variable `MONITOR_ENABLED=true`. Set it to false to pause. This leaves manual runs available.
- Manual options: `initialize` creates a missing state branch only; `force` bypasses the cadence gate; `notify` delivers eligible events. Both force and notify default false. Force never overrides the end-date stop.

The monitor checks every 24 hours in September–October, six hours in November, and one hour in December. It reads the most recent check for each configured provider, including failed checks. A five-minute tolerance accommodates startup jitter. Cadence decisions happen before browser installation. Only enabled BookMyShow checks install Chromium. All times and the end-of-December-18 stop are evaluated in Asia/Kolkata.

Schedules are best effort and can be delayed/dropped. The workflow still wakes after the target date but skips all provider and message calls; disable it after the monitoring period. Future years also fail the configured end-date gate. Public scheduled workflows may become inactive after repository inactivity; check their status before the release window. See [GitHub scheduling documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## State and failure behavior

The `monitor-state` branch contains only versioned `state.json`. Every cloud runner restores a fresh checkout, fetches/validates it, then commits observations and pending events before any sends. Accepted markers require a second successful push. No force-pushes, automatic reset, or automatic reinitialization.

A missing state branch or corrupt file stops the job. A non-fast-forward push or failed acceptance persistence requires investigation; preserve remote history and inspect uncertain claims before resending. See [delivery recovery](PHASE_5_TELEGRAM.md).

The initialization input refuses an existing state branch. Normal runs cannot initialize state. GitHub Actions `contents: write` is scoped to the monitor job. Repository branch rules must permit its state-branch pushes.

Run logs and step summaries show cadence decisions, provider states, check timestamps and sanitized delivery outcomes. Red runs signal provider, state, or delivery failures; they must not be interpreted as ticket unavailability. Confirm recent timestamps in `state.json` to detect stale checks. GitHub’s own workflow failure notifications depend on the account's notification settings; a stopped scheduler cannot send its own Telegram warning.

## Free operation and retention

Use `ubuntu-latest` standard hosted runners in this public repository. [GitHub documents free standard-runner execution for public repositories](https://docs.github.com/en/billing/concepts/product-billing/github-actions). No larger runners, paid broadcasts, artifacts, or Actions dependency caches are enabled. Repository workflow log retention is set to seven days. Runtime is bounded to 15 minutes per monitor job and 10 minutes per CI job. Early-period wakeups still incur a short checkout/setup/gate job; browser/provider work runs only when due.

State history grows with changed observations, capped by the check cadence; unchanged files are not committed. No additional service account or billing setup was created. Recheck allowances if changing repository visibility, enabling artifacts/caches, or choosing a different runner.

## Validation record

- Linux CI passed all 95 tests on the initial cloud run.
- State bootstrap passed and created the dedicated branch.
- [First provider run](https://github.com/SiddhantStark/Doomsday/actions/runs/36542629544): both providers returned `CHECK_FAILED / HTTP_403`; state commit/push succeeded. Job runtime: about 33 seconds including browser installation.
- [Second fresh runner](https://github.com/SiddhantStark/Doomsday/actions/runs/36542754582): same access failures; persisted counters advanced from 1 to 2 for both providers. Queue remained empty and no messages were sent. Runtime: about 39 seconds.
- Local District recheck at 13:56 IST still succeeded with `MOVIE_LISTED` and no target-date shows. The observed District failure is specific to the tested cloud environment; its precise blocking rule is unknown.
- [Cadence-gate run](https://github.com/SiddhantStark/Doomsday/actions/runs/36542865392) succeeded in about 10 seconds and skipped browser installation and provider requests because the daily check was not due.
- Schedule activation is blocked. `MONITOR_ENABLED` remains false. CI remains active.
- Cloud availability-to-alert delivery has not been validated; the two failed checks cannot prove cloud notification deduplication. That behavior is covered locally by transport/state tests, not claimed as live cloud acceptance.

## Blocker and next decision

Do not activate repeated checks against the current blocked providers. Resolve permitted cloud access, or choose a runtime/network that can access District. Local District checks currently work, but using this Mac for scheduling would require it to stay online; the laptop-off goal is not met by that alternative. No anti-bot bypass, paid proxy, or additional account was introduced. Phase 6 remains incomplete until a usable runtime is validated.

## October 2 — Headed cloud diagnostic

[Diagnostic run](https://github.com/SiddhantStark/Doomsday/actions/runs/36988909738) installed Chromium and ran it in headed mode under Xvfb on a standard GitHub Linux runner. All four independently checked pages returned HTTP 403: BookMyShow's Chennai Avengers page and October 2 BSR cinema schedule, and District's Avengers page and October 2 BSR cinema schedule. Both normalized provider results were `CHECK_FAILED / HTTP_403`. Runtime was 35 seconds.

The diagnostic has only contents-read permission, no Telegram secrets, no state checkout, no persistent browser profile, and no notification calls. It writes sanitized status/structure information to job logs, not raw HTML or cookies. No messages were sent and no production state changed. It remains manually callable as `Read-only browser diagnostic`; it is not scheduled.

Visible mode alone does not resolve cloud access. The exact provider filtering rule remains unknown. Phase 6 cannot be marked complete on these results. Scheduling stays disabled until a permitted, usable runtime has been verified. Completing the phase requires a hosting/access decision; local scheduling changes the laptop-off requirement, while supported cloud/API access requires further investigation.
