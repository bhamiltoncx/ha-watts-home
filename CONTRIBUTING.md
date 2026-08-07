# Contributing

## Requirements

Home Assistant 2026.6 requires **Python 3.14.2 or newer**, so the development
environment needs a matching interpreter.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

`requirements-dev.txt` pulls in Home Assistant, pytest, and the async test
helpers via `pytest-homeassistant-custom-component`, plus the integration's own
runtime dependencies (`curl_cffi`, `pydantic`). `.venv/` is gitignored.

## Running tests

```bash
.venv/bin/python -m pytest tests/ -q
```

A subset of tests hit the live Watts API and are skipped unless account
credentials are exported:

```bash
export WATTS_USER=you@example.com
export WATTS_PASS=secret
```

Without them the suite still runs and passes — the credentialed tests report as
skipped. Everything else is mocked or uses fixtures from `tests/fixtures/`.

## Linting and commit hooks

Formatting and linting run through `pre-commit`, which is not part of
`requirements-dev.txt` — install it separately:

```bash
pip install pre-commit
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

Both `--hook-type` flags are needed. The plain `pre-commit install` only wires
up the pre-commit stage, which silently skips the Conventional Commits check
that runs at the commit-msg stage.

The hooks are `ruff` (lint, with `--fix`), `ruff-format`, `prettier` for JSON
and YAML, and `conventional-pre-commit` for commit messages. To check
everything without committing:

```bash
pre-commit run --all-files
```

## Commit messages

Commits follow [Conventional Commits](https://www.conventionalcommits.org/).
The allowed prefixes are `feat`, `fix`, `docs`, `style`, `refactor`, `test`,
`chore`, `ci`, `perf`, and `build`. Releases are cut by release-please from
these prefixes, so the prefix determines the version bump — `feat` produces a
minor bump, `fix` a patch, and a `!` suffix or `BREAKING CHANGE:` footer a major.

## Pull requests

This repo uses stacked PRs — see [AGENTS.md](AGENTS.md#pull-requests) for the
`gh-stack` workflow. Keep PRs small and atomic, open them as drafts, and make
sure each branch is green before committing.

## Regenerating test fixtures

`scripts/dump_fixtures.py` refreshes the recorded API responses in
`tests/fixtures/`:

```bash
WATTS_USER=you@example.com WATTS_PASS=secret .venv/bin/python scripts/dump_fixtures.py
```

Only `devices.json` is tracked in git. `user_details.json` and `locations.json`
are gitignored because they contain account details.

## Testing against a real Home Assistant

Copy the component onto the target instance and restart:

```bash
rsync -av --exclude='__pycache__' custom_components/watts_home/ \
    root@homeassistant.local:/homeassistant/custom_components/watts_home/
```

Changes under `custom_components/` require a full Home Assistant restart — there
is no reload path for an integration's Python code.

## CI

Every push and pull request runs Home Assistant `hassfest` and HACS validation.
Neither needs credentials, so they gate on structure and manifest correctness
rather than on the live API.
