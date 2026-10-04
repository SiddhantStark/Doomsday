# Monitor operating runbook

## Normal operation

The temporary host is this Mac, via `com.doomsday.ticket-monitor`. Keep it awake, logged in, connected, and powered with the lid open. The display may sleep. GitHub scheduling must remain disabled. Local state is authoritative; its old cloud copy is not current.

The LaunchAgent wakes hourly. Provider checks run daily through October, every six hours in November, and hourly in December, with five minutes of cadence tolerance. No terminal window is required. Visible BookMyShow windows open briefly. After December 18 IST, scheduled provider checks and message delivery stop, even when forced. Remove/unload the LaunchAgent after the monitoring period; changing the target date requires explicit operator intent and revalidation of URLs/IDs.

## Inspect health

From the project directory:

```sh
uv run --locked python -m doomsday.health
cat .monitor/last-run.json
launchctl print gui/$(id -u)/com.doomsday.ticket-monitor
```

The health report reads state only and displays successful observations, consecutive failures, unresolved event IDs, and stale checks (configured interval plus two hours). A successful launcher exit can mean `not_due`; check provider timestamps as well. A loaded agent being `not running` between invocations is normal. Logs are `.monitor/monitor.log` and rotated backups (1 MB each, four files total). Launcher-level errors appear in `.monitor/launchd.err.log`.

No independent uptime monitor is configured. If the Mac is off, asleep, logged out, or offline, Telegram cannot reliably warn you. Inspect timestamps after waking/reconnecting. StartInterval wakeups are best-effort, not a precise clock.

## Missing checks or browser errors

1. Confirm power, internet, logged-in desktop, project path and `.venv` availability.
2. Inspect launcher status, logs and last provider timestamps.
3. For missing browser binaries, run `uv run --locked playwright install chromium`.
4. For dependencies, run `uv sync --locked`.
5. Trigger a cadence-aware launch with `launchctl kickstart gui/$(id -u)/com.doomsday.ticket-monitor`.
6. For an immediate independent read-only check, use `uv run --locked doomsday --dry-run --provider all --headed`.

A 403 is a failed check, not unavailable tickets. Do not delete state, transfer browser cookies, or retry continuously to hide it. If a parser reports changed markup, pause repeated manual probes, inspect public-page evidence, update fixtures/parser and rerun the relevant tests. Preserve the prior successful observation through failures. Existing coverage does not prove all future language/format layouts or sold-out markup are supported.

## Telegram problems

`TELEGRAM_401`/invalid credentials: replace the token in local `.env` after reviewing the bot credentials. `TELEGRAM_403`: verify the bot is not blocked and the chat is accessible; open the private chat and start/unblock it. Update `TELEGRAM_CHAT_ID` locally if necessary. Never put credentials in YAML, logs, screenshots, or Git. Old GitHub Secrets are unused while cloud scheduling is disabled; update them separately before a future cloud migration.

A rate-limited pending event carries a retry deadline; do not force repeated runs before it. A failed/uncertain/sending event requires review. Inspect the chat for its logical event ID. A timeout or crash may occur after Telegram accepted the message.

```sh
# Only after confirming the event was received:
uv run --locked doomsday --state .monitor/state.json --resolve-event EVENT_ID --resolution accepted
# Or, after fixing the cause and deciding to retry:
uv run --locked doomsday --state .monitor/state.json --resolve-event EVENT_ID --resolution retry
uv run --locked doomsday --state .monitor/state.json --send-pending
```

Retrying an uncertain send may duplicate a message. Never mark accepted merely to clear an error. Exactly-once delivery cannot be guaranteed across external API and persistence failures. Routine accepted events are not resent across restart.

## Pause, state backup and recovery

Unload first, then wait for the active process to exit before copying/restoring state:

```sh
launchctl bootout gui/$(id -u)/com.doomsday.ticket-monitor
```

Stopping during a send can leave an uncertain claim; review it before resuming. Save a private copy of `.monitor/state.json` outside the working directory. No automatic off-machine backup is configured. Never restore an old copy without comparing event acceptance history: an older snapshot can resend alerts. Missing/corrupt state must fail closed; do not use `--init-state` to discard history. Preserve the damaged file and restore a reviewed known-good snapshot.

Resume:

```sh
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/com.doomsday.ticket-monitor.plist"
```

Unloading alone is temporary; to remain paused across logins, move the plist out of `~/Library/LaunchAgents` after unloading it. Never run local and cloud schedulers concurrently against divergent state. When changing hosts, pause the old host, migrate the latest validated state, verify duplicate suppression and only then enable the new host.

## Observation period and release checks

The 48–72-hour observation period starts October 2 at 18:37 IST, the first successful real LaunchAgent check. Earliest 48-hour review: October 4 at 18:37 IST; preferred 72-hour review: October 5 at 18:37 IST. This is a planned observation period, not a claim that it has elapsed, and no separate reminder has been installed.

Review launcher completion timestamps, daily provider timestamps, errors, state integrity, pending/uncertain events, and duplicate messages. At the current daily cadence, expect approximately 2–3 provider checks over this period; hourly launches generally skip. Record sleep/network interruptions and extend the observation period if they prevent meaningful validation.

Before November and again before December, revalidate the real pages, target identities and complete schedules, then send a separately authorized test message if needed. Do not mistake simulated December availability for real tickets. Keep known access limitations visible. Free operation uses existing hardware and Telegram with paid broadcasts disabled; the Mac still consumes power and internet bandwidth.

## Scheduled results summaries

Enabled October 4 at the user's request via `notifications.status_summaries: true`. Each actual check queues one combined Telegram results summary with provider-specific check times and availability details. A failed check says availability is unknown; it never says tickets are unavailable. A launcher wake that skips as not due sends nothing. Existing first-availability, earlier-show, reappearance and health alerts remain enabled, so a meaningful change can produce its dedicated alert plus the summary.

Summaries use the same durable claim/acceptance/retry mechanism as other events. State schema v3 adds summary results and migrates existing v1/v2 files without discarding history. Older application versions that only support v2 cannot read the upgraded file; do not downgrade without a reviewed migration. A fresh manual check was used to validate the initial summary; this also advances the daily cadence timestamp. This feature change is recorded during the observation period and requires subsequent scheduled delivery observation before declaring it soak-tested.
