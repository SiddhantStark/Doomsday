# Hosting and storage decision — Phase 0

Confirmed with the user: public GitHub repository, no additional service accounts, no paid services, and hourly checks near release with occasional delays accepted.

## Execution

Use standard GitHub-hosted Linux Actions runners; avoid larger paid runners. Schedule hourly near release, at an off-hour minute such as :17. Earlier periods use daily or six-hourly checks. Stop after the target date in Asia/Kolkata. Store credentials only in GitHub Actions Secrets; never run privileged monitoring against untrusted pull-request code.

Public repositories using standard runners qualify for free execution under current [GitHub billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions). Scheduling is best effort and can be delayed or dropped. Public scheduled workflows can also be disabled after repository inactivity; include activation checks in the release runbook. See [scheduled events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

At hourly frequency, expect at most 24 scheduled checks/day, about 744/month. At an estimated 2–5 minutes/run that is 1,488–3,720 runner minutes/month; measure actual runtime later. Avoid routine screenshots/HTML artifacts; retain bounded diagnostics only when necessary and verify storage allowances before deployment. No automatic billing or paid overages.

## Durable state

Implement a small JSON file on a dedicated `monitor-state` branch in Phase 4/6. No separate database account. Keep provider observations, target keys, failure counters, and logical event pending/accepted markers. Public state contains no bot token, chat ID, private Telegram message ID, or raw API responses. Keep precise transport response identifiers in memory only unless a private persistence design is added later.

Use one concurrency group across scheduled/manual monitor runs, with cancellation disabled for an active run. Read current branch state before each run; validate schema; require explicit initialization on first deployment. Missing/corrupt state later must fail closed. Commit pending events before sending and accepted markers after successful sends. Stop if the pre-send state push fails. If a send succeeds but its acknowledgement cannot be persisted, report uncertainty: this architecture cannot promise exactly-once messaging across crashes. Use normal fast-forward pushes, handle conflicts explicitly, and never force-push history automatically.

Grant `contents: write` only to the workflow that persists state. Branch protections must allow the chosen workflow mechanism. State commits are small; persist changed state only and monitor repository growth. Caches/artifacts are not the source of truth. The repository has not been published and no workflow or state branch is created by this planning decision.

## Remaining implementation checks

- Phase 2/3: live extraction and bookability validation.
- Phase 4: state schema, restart/crash behavior, and redaction.
- Phase 6: repository setup, workflow permissions, secrets, runner access to both providers, and free storage allowances.
- Phase 7: soak test, scheduler gaps, inactivity/reactivation checks, and end-date stop.

Phase 0 planning is complete. Deployment reliability is not yet verified.
