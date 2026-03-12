---
name: delivery-prepare
description: Use when preparing a commit or push, including requests like "pre-commit", "prepare commit", "prepare push", or "run checks before push". Produces the shared machine-first `delivery/1` contract consumed by `delivery-closeout`: local delivery evidence plus a valid delivery contract with explicit authority, mode, and typed refs.
---

# Delivery Prepare

## Scope

- This skill is the producer stage of the shared delivery contract.
- It stays path-conditional and runs only the commands explicitly required by the repository layout.
- It produces local delivery evidence plus a valid `delivery/1` message for `delivery-closeout`.

## Hard gate

Do not run `git commit` or `git push` until you have produced a **Delivery-prepare report** (see template below) that includes:

- Every command you ran (or explicitly skipped)
- The exact exit code for each command you ran
- A clear skip reason for each skipped gate

If a gate is not applicable, record it as `skipped` with a reason and do not invent substitute commands.

This repository also requires commit messages to follow the `delivery/1` schema (single-line JSON). Do not use free-form commit messages.

Note: Some checks are **manual reviews** and may not have an exit code. For these, record:

- What you scanned/read (files/paths)
- Your conclusion (impact/no-impact/unclear + risk)

## Always-run preflight (evidence)

Run these commands and record their exit codes in the report:

- `git status --porcelain`
- `git diff --stat`

## Delivery contract gate (required)

Before committing, draft a commit message that is:

- A single-line JSON object (no leading/trailing text)
- `schema` is exactly `delivery/1`
- Contains these keys: `schema,type,scope,summary,intent,impact,breaking,risk,authority,delivery_mode,refs`

Minimum type/shape constraints:

- `breaking`: boolean
- `authority`: exactly `linear`
- `delivery_mode`: one of `closeout`, `status-only`, `reopen`
- `refs`: non-empty array of typed objects
- `risk`: one of `low`, `medium`, `high`

Delivery contract:

- `delivery-closeout` consumes the latest pushed `delivery/1` contract exactly as produced here.
- There must be exactly one Linear authority ref: `{ "system": "linear", "id": "TEAM-123", "role": "authority" }`
- Additional internal refs must be Linear related refs: `{ "system": "linear", "id": "TEAM-456", "role": "related" }`
- GitHub mirror targets must be explicit typed refs: `{ "system": "github", "repo": "owner/repo", "number": 123, "role": "mirror" }`
- Exact duplicate refs are canonicalized by target identity and later repeats are skipped. Conflicting duplicates for the same target are invalid and must fail validation.
- Same-repo shorthand such as `#123`, branch-name inference, PR-title inference, and repo-origin inference are not part of the canonical contract.

Recommended contract generator (prints a single-line JSON message):

- Skill scripts live under this skill's directory (the folder containing this `SKILL.md`).
- Locate that directory via the runtime's skills list and set `DELIVERY_PREPARE_HOME` to it before running these commands.
- `python3 "$DELIVERY_PREPARE_HOME/scripts/build_delivery_contract.py" --type <type> --scope <scope> --summary <summary> --intent <intent> --impact <impact> --risk <low|medium|high> --delivery-mode <closeout|status-only|reopen> --authority-linear-ref <TEAM-123> [--linear-ref <TEAM-456>] [--github-ref <owner/repo#123>]`

Local validation (required; record exit code in the report):

- `python3 "$DELIVERY_PREPARE_HOME/scripts/validate_delivery_contract.py"`

Fallback validation (use only if the script is unavailable; record exit code in the report):

- ```sh
  printf '%s' "$DELIVERY_CONTRACT" | python3 -c '
  import json
  import re
  import sys

  text = sys.stdin.read().strip()
  assert text and "\n" not in text and "\r" not in text, "delivery/1 must be single-line JSON"
  payload = json.loads(text)
  required = "schema type scope summary intent impact breaking risk authority delivery_mode refs".split()
  missing = [key for key in required if key not in payload]
  assert not missing, missing
  extra = sorted(set(payload) - set(required))
  assert not extra, extra
  assert payload["schema"] == "delivery/1"
  assert payload["authority"] == "linear"
  assert payload["delivery_mode"] in ("closeout", "status-only", "reopen")
  assert isinstance(payload["breaking"], bool)
  assert payload["risk"] in ("low", "medium", "high")
  assert all(isinstance(payload[key], str) and payload[key].strip() for key in ("type", "scope", "summary", "intent", "impact"))
  refs = payload["refs"]
  assert isinstance(refs, list) and refs
  linear_re = re.compile(r"^[A-Z][A-Z0-9]*-\d+$")
  github_re = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
  seen = {}
  authority_count = 0
  for ref in refs:
      assert isinstance(ref, dict), "invalid ref object"
      if ref.get("system") == "linear":
          assert set(ref) == {"system", "id", "role"}, "invalid linear ref"
          assert linear_re.match(ref["id"]), "invalid linear ref"
          assert ref["role"] in ("authority", "related"), "invalid linear ref"
          key = ("linear", ref["id"])
      elif ref.get("system") == "github":
          assert set(ref) == {"system", "repo", "number", "role"}, "invalid github ref"
          assert github_re.match(ref["repo"]), "invalid github ref"
          assert isinstance(ref["number"], int) and ref["number"] > 0, "invalid github ref"
          assert ref["role"] == "mirror", "invalid github ref"
          key = ("github", ref["repo"], ref["number"])
      else:
          raise AssertionError("invalid ref object")
      previous = seen.get(key)
      if previous is not None:
          assert previous == ref, ("conflicting duplicate ref", key)
          continue
      seen[key] = ref
      if ref["system"] == "linear" and ref["role"] == "authority":
          authority_count += 1
  assert authority_count == 1
  '
  ```

## Steps

1. `Makefile.toml` exists at repo-root?
    - If present, run **exactly** in this order:
        - `cargo make lint-fix`
        - `cargo make fmt`
        - `cargo make test`
    - If not present, record that the Makefile.toml gate is not applicable and skip this section.

2. `docs/` directory exists at repo-root?
    - If present, perform a **documentation impact review**:
        - Check whether this change requires docs updates (user-facing behavior, config/env vars, CLI, APIs, runbooks).
        - If docs were edited, sanity-check that the edits match the change.
        - If docs were not edited, record why (no docs impact vs. missed update) and the resulting risk.
    - If the repository documents an exact docs-validation command, you may run it, but it is not required. Default to reading/scanning relevant docs content.

3. `.github/workflows/` directory exists at repo-root?
    - If present, perform a **workflow impact review**:
        - Scan workflow definitions to understand what checks CI will run.
        - Use the local commands you already ran (and their results) to infer whether this change is likely to impact CI.
        - If the change plausibly affects CI but your local runs do not cover it, record the gap and risk (and optionally run additional local checks if they are clearly justified).
    - Do not auto-run workflows or use `gh` watchers as a substitute for CI.

`lint-fix` may change files, so keep `fmt` and `test` tied to the same local state.

## Outputs

- Produce a Delivery-prepare report with the following structure:

```
Delivery-prepare report

Preflight
- `git status --porcelain` (exit: <code>)
- `git diff --stat` (exit: <code>)

Commit message
- proposed: `<single-line delivery/1 JSON>`
- validation: ran | skipped: <reason>
  - `python3 "$DELIVERY_PREPARE_HOME/scripts/validate_delivery_contract.py"` (exit: <code> | n/a)
  - fallback validator snippet (exit: <code> | n/a)

Repo gates
- Makefile.toml gate: ran | skipped: <reason>
  - `cargo make lint-fix` (exit: <code> | n/a)
  - `cargo make fmt` (exit: <code> | n/a)
  - `cargo make test` (exit: <code> | n/a)
- docs review: done | skipped: <reason>
  - scanned/read: <paths/files>
  - conclusion: <no-impact|impact|unclear> (risk: <low|medium|high>)
- workflows review: done | skipped: <reason>
  - scanned: <paths/files>
  - conclusion: <no-impact|impact|unclear> (risk: <low|medium|high>)
```
