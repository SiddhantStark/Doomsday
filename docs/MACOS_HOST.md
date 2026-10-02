# Temporary macOS host

The user selected this Mac as the temporary host on October 2, 2026. GitHub scheduling remains disabled (`MONITOR_ENABLED=false`). Cloud access is still unresolved; this deployment requires a logged-in, awake Mac with internet connectivity.

Installed LaunchAgent: `~/Library/LaunchAgents/com.doomsday.ticket-monitor.plist`, label `com.doomsday.ticket-monitor`. It launches the project's existing `.venv/bin/python -m doomsday.macos` at login and every hour. Keep the project and virtual environment at their current paths; moving either requires updating the plist. After dependency changes, run `uv sync --locked`.

The wrapper uses an exclusive whole-run lock, rotating logs (1 MB plus three backups), local durable production state, headed BookMyShow, and Telegram delivery. It uses the existing daily September–October, six-hourly November, hourly December cadence gate, and stops provider/message calls after December 18 IST. Hourly launcher wakeups are only cadence checks until due. macOS may coalesce/delay launches; sleep prevents regular checks. A run after waking checks whether monitoring is due.

The `caffeinate -i` wrapper prevents idle sleep only while a check is running. It does not keep the Mac awake between runs or prevent lid-closure sleep. Keep the lid open and prevent automatic computer sleep on power in macOS settings, or manually run `caffeinate -i` in a terminal while monitoring is needed. The display can sleep. No system power settings were changed by this installation.

## Local files

- `.monitor/state.json`: production history restored from the cloud state branch before the first launch; now the authoritative state while hosting locally.
- `.monitor/monitor.log`: bounded execution logs.
- `.monitor/last-run.json`: latest launcher completion timestamp and exit code; inspect state observation timestamps for the last actual provider check.
- `.monitor/launchd.err.log`: launcher-level errors, normally empty.

These files are ignored by Git. Credentials remain in the existing local `.env`; no secrets appear in the plist. Do not enable cloud monitoring against the older branch state. Before switching hosts, pause the local agent and migrate the latest local state to the destination to preserve deduplication history.

## Operations

```sh
# Inspect registration and last process result:
launchctl print gui/$(id -u)/com.doomsday.ticket-monitor
# Trigger a cadence-aware run now (does not override due time):
launchctl kickstart gui/$(id -u)/com.doomsday.ticket-monitor
# Stop and unload until loaded again or next login:
launchctl bootout gui/$(id -u)/com.doomsday.ticket-monitor
# Load again:
launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/com.doomsday.ticket-monitor.plist"
```

To pause across logins, unload it and move the plist out of `~/Library/LaunchAgents`. Do not delete state to reset the schedule. For an explicit read-only provider check, use `uv run --locked doomsday --dry-run --provider all --headed`.

## Validation

First real LaunchAgent run on October 2 at 18:37 IST exited 0. BookMyShow returned COMING_SOON and District MOVIE_LISTED. Both observations were saved locally, failure counters recovered, and no events/messages were produced. A second real invocation at 18:38 IST exited 0 with `not_due`, without another provider check or message. No synthetic data was injected into production state. Automated tests cover the local scheduler argument routing and sanitized launcher error status in addition to existing state/delivery tests.

This is an operational local replacement for the cloud host. It does not establish laptop-off reliability. The 48–72-hour observation period and any new live notification acceptance exercise remain separate readiness checks; the Phase 5 Telegram test was already user-confirmed.
