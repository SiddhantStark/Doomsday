# Phase 5 — Telegram alerts

Implemented September 29, 2026. Telegram is the only notification transport; paid broadcasts are explicitly disabled. Credentials are loaded from the private environment, never from public state.

## Run

Record checks and send eligible queued events:

```sh
uv run --locked doomsday --provider district --state .monitor/state.json --notify
```

Use `--init-state` only for the first run and `--provider all` for all enabled providers. Without `--notify`, checks continue to record events without sending. The Git backend accepts `--state-repo /path/to/dedicated-checkout` instead of `--state` and requires successful remote persistence before sending.

Retry the existing queue without checking providers:

```sh
uv run --locked doomsday --state .monitor/state.json --send-pending
```

`notifications.enabled: false` disables delivery and leaves events queued. Dry runs and fixture commands cannot send; synthetic state is rejected by the sender. Only the configured target and enabled providers are eligible. Superseded or expired availability events are marked skipped rather than sent late. Health events are skipped if the provider has recovered. A successful provider observation is still needed to establish availability; failed checks cannot establish disappearance.

The queue processes at most 20 candidates per invocation. Permanent/uncertain entries remain visible as delivery problems and are not automatically resent. A retry delay stops processing until its deadline, so a rate-limit response is not immediately retried by another queue event.

## Message and acceptance behavior

Messages include the movie, venue/city, provider, target date, earliest bookable show and booking URL (for availability events), checked-at time in IST, and a logical event ID. No Markdown parsing is enabled. First availability, earlier shows, and reappearance have distinct titles. Three consecutive provider failures create one health event per failure streak; successful recovery resets that streak.

Before sending, the event is durably changed from pending to sending. Only after that save/push succeeds does the HTTP request run. API success marks it accepted; Telegram message IDs are discarded and never added to public state. API acceptance does not prove device delivery or human receipt. This follows the [Telegram sendMessage contract](https://core.telegram.org/bots/api#sendmessage).

Explicit transient API rejections use the configured bounded retry policy. Rate limits respect [retry_after](https://core.telegram.org/bots/api#responseparameters). Delays longer than 60 seconds are persisted for a later invocation rather than blocking the process. Invalid token, blocked bot, invalid chat/request, and similar permanent failures require operator action.

Transport exceptions, timeouts, and malformed responses can have ambiguous outcomes and are recorded as uncertain without an automatic resend. A crash after the durable claim leaves sending. A failure to save acceptance also leaves a claim that requires review. This avoids blindly resending after an ambiguous send, but cannot guarantee exactly-once delivery.

Exit 4 indicates delivery problems; exit 3 indicates state/persistence failure. Counts use `messages_accepted`, never a claim of device delivery. Console logs and JSON output contain sanitized error codes, not token-bearing URLs or raw Telegram responses.

## Recovery

Inspect the Telegram chat and the logical event ID before resolving a sending/uncertain event. After fixing credentials or unblocking the bot, a permanently failed event can be explicitly retried. Preserve state and investigate Git push failures before continuing.

```sh
# If the event was received, record acceptance without sending again:
uv run --locked doomsday --state .monitor/state.json --resolve-event EVENT_ID --resolution accepted
# If you decide a retry is appropriate (an uncertain prior send may duplicate):
uv run --locked doomsday --state .monitor/state.json --resolve-event EVENT_ID --resolution retry
uv run --locked doomsday --state .monitor/state.json --send-pending
```

State schema v2 adds attempt counts, sanitized error codes, retry deadlines, and delivery states. Valid v1 pending/accepted histories migrate without losing events; the upgrade is persisted on the next writable transaction. Dry-run reads never rewrite the file. Malformed legacy state still fails closed.

## Live test

The user authorized one explicitly labeled test. On September 29, the new notifier sent `TEST — Doomsday Ticket Monitor` with the configured target and District movie link; Telegram returned API acceptance. No production state was changed. The user confirmed receipt and that the movie, venue, date, and link looked correct.

For a future explicitly requested test, use `uv run --locked doomsday --telegram-test`. It sends a clearly labeled test without creating production availability events. Do not automatically repeat a test after an uncertain outcome.

## Verification

Mocked transport tests cover API success, invalid token, blocked bot, rate limits and persisted cooldowns, transient failures with bounded backoff, ambiguous timeout/response handling, formatting, disabled notifications, synthetic isolation, duplicate suppression, durable pre-send claims, post-send persistence failure, operator resolution, stale events, and legacy-state migration. No tests contact Telegram.

Cloud scheduling and cross-runner concurrency remain Phase 6. BookMyShow standalone access still has its Phase 2 HTTP 403 blocker.
