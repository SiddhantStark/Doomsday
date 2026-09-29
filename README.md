# Doomsday Ticket Monitor

Python application for monitoring Avengers: Doomsday at BSR Thoraipakkam on December 18, 2026. Telegram is the only alert channel. **BookMyShow read-only checks are implemented but currently blocked by HTTP 403 in standalone Chromium. District read-only checks are implemented and locally live-validated. Durable JSON/Git state and change detection are implemented. Telegram delivery from the event queue is implemented. GitHub Actions infrastructure is deployed, but scheduled monitoring is disabled because both providers return HTTP 403 from GitHub runners.**

## Local setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/). The project supports Python 3.12+ and selects Python 3.13 for development via `.python-version`. From this directory:

```sh
uv sync --locked
```

Use the existing private `.env` for credentials. On a fresh checkout, copy `.env.example` to `.env` and fill it locally. Fixture previews require no credentials. Never commit `.env` or paste its contents into logs.

`uv sync` manages `.venv` and installs the project plus the default `dev` dependency group. No manual activation is needed. Commit `pyproject.toml`, `.python-version`, and `uv.lock`; keep `.venv` ignored.

## Dependency management

```sh
uv add <package>
uv add --dev <package>
uv remove <package>
uv lock --upgrade-package <package>
uv sync --locked
```

Use `uv sync --locked --no-dev` for deployment and `uv run --locked --no-dev ...` for its commands. `--locked` rejects stale lockfiles instead of resolving new versions. The lockfile pins application dependencies; the Python patch release and isolated build tooling are not pinned by it.

## Run the foundation

```sh
uv run --locked python main.py --once --dry-run --fixture tests/fixtures/preview.json
# Equivalent installed command:
uv run --locked doomsday --dry-run --fixture tests/fixtures/preview.json
```

The fixture is synthetic normalized data, not a scraped response or evidence of ticket availability. Output is JSON on stdout; structured redacted logs go to stderr. It demonstrates a sold-out 07:00 show being excluded in favor of the bookable 09:00 show. Preview events assume no previous state; full change detection is Phase 4. No network calls, messages, or state writes occur. Repeated previews intentionally repeat their illustrative events.

Running `uv run --locked python main.py --once` without fixture preview mode exits with code 2 because scheduled monitoring is not yet available; select a provider explicitly for a read-only check. Successful previews exit 0; invalid configuration/fixtures exit 2.

## BookMyShow read-only check

```sh
uv run --locked playwright install chromium
uv run --locked doomsday --once --dry-run --provider bookmyshow
```

Unlike fixture previews, this performs public browser requests but sends no messages or state writes. A provider failure exits 1 and reports `CHECK_FAILED`; it never means tickets are unavailable. See [Phase 2 validation and limitations](docs/PHASE_2_BOOKMYSHOW.md). Browser dependencies are installed separately from Python dependencies.

## Configuration

`config/monitor.yml` defines the target, strict venue aliases, enabled providers, retry settings, Telegram settings, and IST schedule bands: daily in September–October, every six hours in November, hourly in December. The CLI reports the configured interval; it does not schedule or sleep. Paid broadcasts and intervals shorter than one hour are rejected. Unknown configuration fields are rejected, keeping credentials out of YAML.

## Checks

```sh
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
```

## Deployment decision

Use a public GitHub repository, standard Linux Actions runners, and a small JSON state file on a dedicated `monitor-state` branch. Serialize runs and keep credentials, chat IDs, private message IDs, and raw response bodies out of public state. A logical event acceptance marker is sufficient for public deduplication. Only push state changes when needed; fail clearly on persistence errors. Details: [hosting/storage plan](docs/HOSTING_STORAGE.md).

## Layout

- `src/doomsday/`: validated models, configuration, CLI, time and logging utilities.
- `config/monitor.yml`: non-secret target and runtime configuration.
- `tests/fixtures/`: synthetic previews and reduced public provider responses.
- `docs/`: feasibility evidence, Telegram setup, hosting decision.
- [ROADMAP.md](ROADMAP.md): completed work and next phases.

Next: resolve the Phase 6 cloud access blocker before enabling scheduled monitoring. BookMyShow live acceptance remains blocked.

## District and combined read-only checks

```sh
uv run --locked doomsday --once --dry-run --provider district
uv run --locked doomsday --once --dry-run --provider all
```

District uses public HTTPS pages without a browser. `all` checks every enabled provider independently and exits 1 if any fails, while preserving successful results. These commands never send alerts or write state. See [Phase 3 evidence and limitations](docs/PHASE_3_DISTRICT.md).

## Persistent observations (Phase 4)

```sh
# First run only:
uv run --locked doomsday --provider district --state .monitor/state.json --init-state
# Subsequent runs:
uv run --locked doomsday --provider district --state .monitor/state.json
```

This records observations and pending events but sends no messages. Missing/corrupt history fails closed; never reinitialize to hide a state error. Use a separate synthetic state file for fixtures. State-aware dry runs and the dedicated Git branch backend are documented in [Phase 4 usage and recovery](docs/PHASE_4_STATE.md).

## Telegram delivery (Phase 5)

```sh
uv run --locked doomsday --provider district --state .monitor/state.json --notify
uv run --locked doomsday --state .monitor/state.json --send-pending
```

These commands send eligible production events to the configured Telegram chat. State must already exist (or be explicitly initialized with the provider command). Without `--notify`, checks remain record-only. Dry runs and synthetic state cannot send. See [Phase 5 usage, retries, and uncertain-send recovery](docs/PHASE_5_TELEGRAM.md).

## Cloud deployment status

[Public repository](https://github.com/SiddhantStark/Doomsday) · [Workflow runs](https://github.com/SiddhantStark/Doomsday/actions)

CI, private Actions Secrets, and the durable state branch are deployed. Two fresh cloud runs preserved state correctly but both providers returned HTTP 403. District still works locally. `MONITOR_ENABLED=false` keeps scheduled checks paused; manual runs remain available. See [Phase 6 evidence and operations](docs/PHASE_6_DEPLOYMENT.md).
