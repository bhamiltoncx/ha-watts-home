# AGENTS.md

Guidance for coding agents working in this repository.

## What this is

A Home Assistant custom integration for Watts Home (Tekmar) thermostats, living
under `custom_components/watts_home/`. Tests are pytest-based in `tests/`.

[CONTRIBUTING.md](CONTRIBUTING.md) is the source of truth for environment setup,
dependency installation, commit hooks, and fixture regeneration. Read it first if
the working environment is not already set up; this file covers only what differs
for agents.

## Pull requests

This repo uses **GitHub stacked PRs** via the [`gh-stack`][gh-stack] CLI
extension. Prefer small, atomic PRs: each one addresses a single issue or adds a
single feature, with tests. When a change spans multiple concerns, split it into
a stack of branches rather than opening one large PR — each branch maps to one
PR whose base is the branch below it, so reviewers see only that layer's diff.

Install the extension and its accompanying agent skill with:

```bash
gh extension install github/gh-stack && gh skill install github/gh-stack
```

Install instructions and full command reference: <https://github.com/github/gh-stack>

Typical flow:

```bash
gh stack init <bottom-branch>   # create the stack
git add … && git commit         # commit the bottom layer
gh stack add <next-branch>      # add a layer on top
git add … && git commit
gh stack submit --auto          # push and open draft PRs
```

Agents must run `gh stack` non-interactively: pass branch names as positional
arguments, use `--auto` with `submit`, and `--json` with `view`. Without those
flags the commands prompt or open a TUI and will hang.

Open PRs as drafts. Keep PR bodies terse and factual — what changed and why.

## Conventions

- Commit messages follow Conventional Commits — the `conventional-pre-commit`
  hook rejects anything else. See [CONTRIBUTING.md](CONTRIBUTING.md#commit-messages)
  for the allowed prefixes and how they drive releases.
- `ruff` lints and formats Python; `prettier` covers JSON and YAML. Run
  `pre-commit run --all-files` before committing.
- Comments should be minimal — short _why_ comments for non-obvious constraints
  only, not narration of what the code already shows.
- `strings.json` and `translations/en.json` are kept identical. A change to one
  needs the same change in the other, or the UI renders raw translation keys.

## Testing

```bash
.venv/bin/python -m pytest tests/ -q
```

Every branch in a stack should be green before it is committed. Some tests hit
the live Watts API and are skipped unless `WATTS_USER` and `WATTS_PASS` are set;
a run that reports skips is expected, not a failure. Prefer mocking over adding
new credential-gated tests, so coverage holds without an account.

See [CONTRIBUTING.md](CONTRIBUTING.md#running-tests) for setup and credentials.

[gh-stack]: https://github.com/github/gh-stack
