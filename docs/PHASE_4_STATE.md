# Phase 4 — Durable observations and event queue

Implemented September 29, 2026. This phase added storage; [Phase 5](PHASE_5_TELEGRAM.md) now implements delivery. Record-only commands below retain their behavior.

## Local usage

Initialize once, recording a real District observation:

```sh
uv run --locked doomsday --once --provider district --state .monitor/state.json --init-state
```

Subsequent checks must omit `--init-state`. Use `--provider all` to record both enabled providers. Provider failures still persist their diagnostic counters and do not prevent successful provider observations from being recorded; the command exits 1 for partial failure.

```sh
uv run --locked doomsday --once --provider district --state .monitor/state.json
uv run --locked doomsday --once --dry-run --provider district --state .monitor/state.json
```

A state-aware dry run reads existing state, computes proposed events, and does not replace the JSON. It may create the parent directory and lock file. Dry runs cannot initialize state. Existing read-only commands without `--state` retain their previous behavior.

For an isolated synthetic exercise:

```sh
uv run --locked doomsday --fixture tests/fixtures/preview.json --state .monitor/test.json --init-state
uv run --locked doomsday --fixture tests/fixtures/preview.json --state .monitor/test.json
```

The second invocation creates no new events. Synthetic and production namespaces cannot be mixed. Synthetic events are development data and must never be delivered. State lives in the ignored `.monitor/` directory in these examples.

## Change detection

Each provider/movie/city/venue/date has its own key. Successful observations determine first availability, a newly earlier bookable show, and availability after a confirmed disappearance. Later shows and unchanged checks create no event. Failed checks increment a counter and preserve the previous successful result. Stale or repeated timestamps are ignored. An unknown-only show status is not treated as evidence of disappearance.

An event contains the target, earliest show, observation, unique ID, and pending/accepted marker. Queue persistence occurs with the observation in one atomic file replacement. Acceptance is tracked independently via `mark_accepted`; accepting an event twice is harmless. Phase 5 will call this only after Telegram API acceptance. No chat ID, token, Telegram message ID, or raw response body is part of the state schema. Events are recorded even when delivery is disabled, so a future delivery policy can handle the pending queue explicitly.

Exit codes: 0 successful run, 1 provider failure, 2 configuration/argument failure, 3 state validation, locking, or persistence failure.

## Storage and recovery

JSON is schema-versioned and validated on load. Initialization refuses to overwrite existing state. Missing or corrupt history fails closed; never automatically initialize after a previously working deployment. Restore the last known good file or branch revision after investigating. Preserve the damaged file for diagnosis without publishing credentials.

A nonblocking OS lock serializes local transactions. Process exit releases it; the lock file may remain and must not be deleted while a run is active. Files are written through a temporary sibling, flushed, atomically replaced, then the directory is flushed. Exceptions before replacement preserve the original. A crash after replacement can leave the new state committed; stable pending event IDs survive restart. This backend targets macOS/Linux, not Windows or distributed filesystem locking.

## Dedicated Git state branch

`--state-repo PATH` accepts an existing dedicated checkout of `monitor-state` with an `origin` remote and an already-created remote branch. Configure its Git commit identity and authentication during Phase 6. Do not point it at the source checkout. Initialization uses `--init-state`; subsequent runs must omit that flag.

```sh
uv run --locked doomsday --provider all --state-repo /path/to/state-checkout --init-state
```

The backend locks the checkout, requires clean tracked files, fetches the state branch, fast-forwards, rejects unpushed/diverged local history, validates/updates `state.json`, and commits/pushes only when changed. Pushes never force history. Git errors are sanitized to avoid exposing credential-bearing remote URLs. Pending events become available to a future sender only after the transaction, including the push, succeeds.

On push failure, preserve the checkout and reconcile its local commit against the remote before retrying. Do not delete pending events or reset history blindly. Cross-machine runs need the shared Actions concurrency group specified in the hosting plan; local locks alone cannot coordinate separate runners. A non-fast-forward push stops the losing run.

After a future message send, accepted markers must also be pushed. If sending succeeds but persistence fails, delivery is uncertain; this design cannot guarantee exactly-once Telegram delivery. Phase 5 must handle that uncertainty explicitly.

The Git backend was tested with a temporary local bare remote and fresh checkout, including push failure recovery behavior. No public remote, real state branch, workflow, or production state was created during Phase 4 implementation. Actual GitHub permissions and runner durability remain Phase 6 deployment checks.

## Verification

The acceptance sequence unavailable → available → unchanged → earlier → failed → unchanged → unavailable → available produces exactly three events across restarts. Tests also cover missing/corrupt state, explicit initialization, namespace isolation, stale checks, unknown statuses, failed writes, overlapping transactions, acceptance persistence, dry-run isolation, provider independence, and Git restoration/failure behavior.
