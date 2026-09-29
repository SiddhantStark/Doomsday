# Phase 0 — Feasibility findings

Checked September 28, 2026. Status: Phase 0 planning complete; Telegram setup verified. Production access validation remains for later phases. No accounts were created, messages sent, or tickets reserved.

## Decision

Proceed with the local foundation. District has a promising HTTP extraction path. BookMyShow needs a normal browser-based implementation and deployment-environment validation because a plain HTTP request returned 403. Neither provider is proven reliable for unattended cloud operation yet. Telegram setup and hosting/storage decisions are complete; see [hosting/storage decision](HOSTING_STORAGE.md).

## Evidence

| Check | BookMyShow | District |
|---|---|---|
| Venue page in browser | Loaded without sign-in or CAPTCHA | Loaded without sign-in or CAPTCHA |
| Venue identity | Cinepolis: BSR Mall, OMR, Thoraipakkam; CBMC in URL | Cinepolis BSR Mall OMR; Thoraipakkam address; CD9505 in URL |
| Target movie | Avengers: Doomsday; ET00439706 | Avengers: Doomsday; MV176735 |
| Target movie page | December 18, 2026 release; interest prompt instead of booking control | December 18, 2026 release; no showtime selector observed |
| Current venue schedule | September 28 selected; September 29–30 enabled | September 28–30 date links |
| Development example | Heart of the Beast: 13:30, 16:55, 22:20; English, 2D | Same movie and times shown |
| Plain HTTPS GET using curl | HTTP 403; no venue/showtime text | HTTP 200; venue, 01:30 PM, and `__NEXT_DATA__` present in HTML |
| Proposed implementation | Normal Playwright navigation and rendered DOM, conditional on successful runtime test | Parse public HTML or embedded page JSON first; browser fallback only if needed |

Source pages:

- [BookMyShow venue](https://in.bookmyshow.com/cinemas/chennai/cinepolis-bsr-mall-omr-thoraipakkam/buytickets/CBMC/20260928)
- [BookMyShow target movie](https://in.bookmyshow.com/movies/chennai/avengers-doomsday/ET00439706)
- [District venue](https://www.district.in/movies/cinepolis-bsr-mall-omr-thoraipakkam-chennai-in-chennai-CD9505)
- [District target movie](https://www.district.in/movies/avengers-doomsday-movie-tickets-MV176735)

These observations establish that the movie is listed and current venue schedules are readable. They do not establish December 18 ticket availability. The sample movie must remain isolated from production target matching. Search-engine snippets were used only for discovery; browser pages were checked directly.

## Extraction and correctness requirements

1. Match provider movie IDs and full title; never match merely “Avengers.” Endgame: Encore is a separate current listing.
2. Add the verified Cinepolis names to venue aliases and retain provider venue IDs. Match city/address as well as name; “Cinepolis” alone is too broad.
3. Validate the selected full calendar date from the page, not just the requested URL. Reject a fallback to today's listings. December 18 was not offered in the inspected date strips.
4. Extract showtime within its movie/language/format group. Compare timezone-aware date/time values in Asia/Kolkata.
5. The current UI exposes book/showtime buttons and availability legends. A legend alone does not prove an individual show is available. Phase 2/3 must validate enabled controls and per-show status fields against live rendered output, including sold-out examples.
6. Use the movie or venue page as a durable booking link initially. District exposes a session seat-layout link, but its longevity is unverified. No seat selection or reservation was attempted.
7. HTML containing `__NEXT_DATA__` is a candidate source, not a guaranteed schema contract. Confirm exact keys during implementation and detect schema changes explicitly.
8. On 403, CAPTCHA, parse failure, or wrong-date fallback, return CHECK_FAILED or an appropriately verified unavailable state; never silently manufacture unavailable tickets. Do not bypass access controls.

## Access limitations and follow-up

- Initial sandbox HTTP attempts failed DNS resolution. Approved network access reached the sites, but this Python installation's certificate trust failed validation. curl succeeded with TLS verification enabled. Fix Python CA configuration during environment setup; do not disable certificate verification.
- A local in-app browser is not the future headless cloud runner. Run one low-frequency access test from the intended deployment environment before declaring either integration ready.
- BookMyShow's HTTP 403 is an explicit blocker for plain HTTP extraction in this environment. If normal browser access is also blocked in deployment, report the provider as degraded and reassess supported access.
- No documented public ticket API was established during this pass. No internal API probing was performed.
- Confirm acceptable automation use with platform documentation before production activation. Technical readability does not grant an API integration contract.
- December 18 showtime extraction must be verified when that date becomes available. Until then use isolated fixtures and current listings.

## Telegram dependency

Telegram is now the only external alert channel, with a zero-cost operating constraint. The user confirmed bot creation and starting its private chat. The token was accepted by Telegram and the private chat ID was saved in the ignored local .env. See [Telegram setup](TELEGRAM_SETUP.md). Earlier business-account onboarding is no longer required.

## Phase 0 completion checklist

- [x] Inspect movie and venue pages on both platforms.
- [x] Compare plain HTTP with browser access and document limitations.
- [x] Identify a current movie for isolated development examples.
- [x] Record matching and bookability validation requirements.
- [x] Prepare Telegram setup instructions.
- [x] Create bot and start private chat (confirmed by user).
- [x] Securely configure token and retrieve chat ID (verified through Telegram getUpdates).
- [x] Select public GitHub Actions standard Linux runners, hourly near release, and JSON on `monitor-state`, with no additional accounts or paid services.

The user created and started the bot. Telegram accepted one user-authorized test alert, and the user confirmed receipt in the private chat. Phase 1 can proceed with fixtures while bot setup is completed. Deployment-environment access remains to be validated in later phases.
