# Development Roadmap

Avengers: Doomsday Ticket Monitoring Agent · September 28, 2026

Product specification: [PRD](<PRD — Avengers_ Doomsday Movie Ticket Monitoring Agent.md>).

## Build approach

Build a Python command-line application that performs one monitoring run and exits. Keep provider extraction, normalized results, change detection, persistence, and notification delivery separate. A scheduler invokes the same application locally or in the cloud. Start with deterministic fixtures, then verify live providers independently. Telegram is the only external alert channel. Console/workflow logs provide operational diagnostics. Use only free services and verified free hosting/storage allowances; do not enable paid overages or broadcasts.

Target: Avengers: Doomsday, Chennai, BSR Thoraipakkam, December 18, 2026, earliest bookable show. These are configurable product targets; confirm listings and date during live validation.

The intended order is Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7. Telegram setup starts in Phase 0 and can proceed while code is developed. Phase 8 is optional. Phase 0 reconnaissance is recorded in [feasibility findings](docs/PHASE_0_FEASIBILITY.md); Telegram setup and a user-confirmed test alert are complete; hosting/storage planning is complete; see [the decision](docs/HOSTING_STORAGE.md).

## Phase 0 — Validate feasibility and start Telegram setup

Estimated effort: 1–2 engineering days; provider-access investigation may add time.

- [x] Inspect publicly accessible BookMyShow and District movie, date, venue, and show listings manually.
- [x] Compare HTTP/HTML and browser access; document the candidate approach and access limitations for each provider. Deployment validation remains pending.
- [x] Identify an isolated current-movie development example; synthetic fixture data must never trigger production alerts.
- [x] Identify bookability and target-date/venue validation requirements. Per-show status mapping remains for provider implementation; do not infer availability from a movie landing page alone.
- [x] Create a bot through @BotFather and start a private chat (confirmed by user).
- [x] Store the bot token and retrieve the chat ID securely (verified through Telegram getUpdates).
- [x] Confirm Telegram setup and receipt of one authorized test alert.
- [x] Select public GitHub Actions standard Linux runners and JSON on a dedicated `monitor-state` branch; hourly near release, no extra accounts, no paid broadcasts. See [hosting/storage decision](docs/HOSTING_STORAGE.md).

Deliverables: [provider feasibility notes](docs/PHASE_0_FEASIBILITY.md) and [Telegram setup checklist](docs/TELEGRAM_SETUP.md). Telegram setup and a user-confirmed test alert are complete. Phase 0 planning is complete; runtime deployment validation remains in later phases.

Exit gate: each provider has an evidence-backed extraction approach or an explicit blocker. Do not promise working monitoring for a blocked provider or bypass its protections. If both are blocked, reassess data access before building the full service.

## Phase 1 — Build the foundation

Status: complete. Validated with 16 tests, Ruff, and a local synthetic dry run.

- [x] Create the Python package, uv project configuration and lockfile, `.gitignore`, `.env.example`, and README.
- [x] Add validated YAML configuration for target, aliases, providers, retry policy, schedule bands, and notification channels.
- [x] Define typed provider results, show statuses, monitoring states, and notification events.
- [x] Implement structured, redacted logging and Asia/Kolkata-aware date/time handling.
- [x] Add one-run and dry-run CLI modes; dry run prints intended events without sending messages or advancing production notification state.
- [x] Create sanitized fixtures and basic validation tests.

Deliverable: a local run that loads configuration and processes fixture results through console output.

Exit gate: invalid configuration fails clearly; no real credentials or outbound messaging are required for development.

## Phase 2 — Implement BookMyShow

Status: implementation tested; live acceptance blocked by HTTP 403. See [Phase 2 validation](docs/PHASE_2_BOOKMYSHOW.md).

- [x] Implement the shared provider interface using the simplest validated access method.
- [x] Locate the movie, selected calendar date, and normalized venue aliases.
- [x] Extract showtimes, explicit booking status, and available booking links.
- [x] Normalize 12/24-hour times and choose the earliest bookable show; exclude sold-out, unknown, and unavailable shows.
- [x] Handle missing listings, unexpected markup, timeouts, and blocked access as distinct outcomes.
- [x] Test reduced observed DOM fragments and synthetic edge cases, including wrong dates/venues and malformed show data.

Deliverable: one run reports a normalized BookMyShow result. Standalone live validation currently returns CHECK_FAILED / HTTP_403.

- [ ] Pass the live acceptance gate on an accessible complete schedule, including sold-out examples and language/format coverage.

Exit gate: live read-only validation succeeds for an accessible listing, target absence is handled truthfully, and fixtures verify edge cases. A successful fixture test alone does not satisfy live readiness.

## Phase 3 — Implement District

Status: complete for local read-only integration. Live target and current-show extraction verified; see [Phase 3 validation](docs/PHASE_3_DISTRICT.md).

- [x] Implement equivalent movie/date/venue/show extraction for District.
- [x] Add provider-specific fixtures and failure cases.
- [x] Ensure one provider's failure does not prevent the other's processing. Alert delivery will be implemented in Phase 5.
- [x] Keep parsers independent from state and notification code.

Deliverable: a single invocation returns both provider results.

Exit gate: live validation succeeds and a simulated BookMyShow failure still allows a valid District result to proceed.

## Phase 4 — Add durable state and change detection

Status: implemented and tested locally, including a temporary Git remote. See [state usage and recovery](docs/PHASE_4_STATE.md). Actual GitHub deployment remains Phase 6.

- [x] Track each provider independently, keyed by target movie, venue, date, and platform.
- [x] Detect first availability, an earlier bookable show, and genuine disappearance followed by reappearance.
- [x] Preserve the last successful observation through failed checks. Repeated identical results must not create new events.
- [x] Persist events before sending; track notification progress separately from current availability.
- [x] Use local JSON and the selected `monitor-state` branch for cloud persistence. Document restoration, public-data minimization, concurrency, and failure behavior; no extra storage account.
- [x] Test restart recovery, missing/corrupt state, and overlapping runs. Stop with an explicit state error rather than silently losing notification history.

Deliverable: a tested state machine and persistent event queue.

Exit gate: unavailable → available → unchanged → earlier show → failed check → unchanged → unavailable → available yields exactly the intended events across restarts.

## Phase 5 — Integrate Telegram alerts

Status: implementation and automated validation complete. One authorized live test was accepted by Telegram and the user confirmed receipt with correct details/link. See [delivery and recovery](docs/PHASE_5_TELEGRAM.md).

- [x] Implement `TelegramNotifier` with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from environment variables.
- [x] Format availability, earlier-show, and health messages with the correct booking link and IST timestamp.
- [x] Record successful API acceptance; keep returned `message_id` private and out of public state; do not claim device delivery or human-read confirmation.
- [x] Implement bounded retries and rate-limit `retry_after` handling; distinguish permanent rejection and ambiguous timeouts.
- [x] Keep failed events recoverable and visible in logs. No email or other external fallback is in scope.
- [x] Test success, 429, blocked bot, invalid token, timeout, and duplicate suppression with mocks.
- [x] Send one explicitly authorized test message to the configured private chat (API accepted September 29).
- [x] Confirm the new test is visible on the recipient's device and details/link are correct (user confirmed September 29).
- [x] Keep paid broadcasts disabled and redact token-bearing URLs from logs.

Deliverable: a test event reaches the Telegram chat with correct values and a usable link.

Exit gate: the recipient confirms the test message, acceptance/error tracking works, and retry/deduplication tests pass. No delivery-status polling or business approval is required.

## Phase 6 — Deploy scheduled execution

Estimated effort: 1–2 days. Depends on Phases 4–5.

- [ ] Add manual and scheduled GitHub Actions entry points, locked dependencies via `uv sync --locked --no-dev`, and Playwright installation only if needed.
- [ ] Configure secrets and restore/persist the chosen durable state backend on every run.
- [ ] Serialize manual and scheduled executions; avoid cancelling an active send midway.
- [ ] Implement the PRD's date-based check frequency and configure timezone conversion explicitly.
- [ ] Add run timeouts, meaningful exit codes, bounded diagnostic retention, and stale-check visibility.
- [ ] Verify the actual account/repository free runner and storage allowances against measured runtime and schedule; reduce usage or stop if necessary, without enabling billing.
- [ ] Test two fresh runner executions against the same state; verify the second does not resend the first alert.

Deliverable: unattended cloud monitoring continues with the laptop offline.

Exit gate: scheduled runs, state recovery, and deliberate provider/message failures behave correctly. GitHub Actions schedules are best-effort; measure delays and decide whether a dedicated scheduler is needed before the critical booking window.

## Phase 7 — Verify readiness and operate

Estimated effort: 2–3 engineering days plus a 48–72-hour observation period. Depends on Phase 6.

- [ ] Run all acceptance scenarios, including wrong venue/date, sold-out shows, earlier shows, reappearance, provider isolation, and delivery failures.
- [ ] Simulate target availability end to end with isolated test state; avoid mixing test events with production history.
- [ ] Soak-test cloud checks for 48–72 hours; inspect check timing, parser reliability, persistence, retries, and duplicate suppression.
- [ ] Record known access limitations. Never label a blocked provider healthy or unavailable.
- [ ] Write a runbook for credentials, blocked bot or invalid token, parser changes, missed runs, state recovery, pause/resume, and costs.
- [ ] Configure an end-of-target-date stop in Asia/Kolkata, with explicit extension if desired.
- [ ] Revalidate live provider pages and Telegram alerts before increasing monitoring frequency.

Deliverable: completed acceptance checklist and operating runbook.

Exit gate: no unresolved critical issues; enabled providers and notifications are verified. Future target availability can only be validated when it exists; fixture demonstrations must be clearly labeled.

## Phase 8 — Optional Docker and scheduler portability

Estimated effort: 1 day. Follow Phase 7 unless scheduling reliability requires it earlier.

- [ ] Package the same one-run command and any browser dependencies in Docker.
- [ ] Document required secrets and persistent storage.
- [ ] Deploy to a dedicated scheduled runtime if measured GitHub Actions reliability is inadequate.
- [ ] Repeat restart and duplicate-prevention checks after migration.

Deliverable: portable execution with equivalent state and alert behavior.

## Planning and milestones

Allow approximately **11–17 engineering days for Phases 0–7**, plus access investigations and soak observation. This is an estimate; provider access is the largest uncertainty. A learning-oriented pace may take longer.

| Milestone | Completion evidence |
|---|---|
| Feasibility established | Provider access notes; Telegram setup started |
| Local monitoring works | Both providers produce verified normalized results |
| Alerts work | Telegram test message received; API acceptance and failures tracked |
| Unattended MVP works | Fresh cloud runs preserve state and avoid duplicates |
| Release-ready | Acceptance checklist and soak test completed |

Aim to finish the MVP in October, begin low-frequency operation in November, and revalidate before increasing December frequency. Start with Phase 0: it determines whether the planned integrations can work before substantial implementation effort.

References: [Telegram bots](https://core.telegram.org/bots), [Bot API](https://core.telegram.org/bots/api), [Telegram limits](https://core.telegram.org/bots/faq), [GitHub scheduled events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
