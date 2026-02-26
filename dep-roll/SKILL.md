---
name: dep-roll
description: Use when upgrading dependencies across multiple ecosystems or regenerating lockfiles where ordering and verification matter.
---

# Dep Roll

## Objective

Perform version constraint and lockfile updates in a disciplined order so dependency bumps stay intentional and auditable.

## When to use

- You are upgrading direct dependency constraints or refreshing package versions.
- You need to align local dependency changes with Dependabot and existing automation.
- Multiple ecosystems in one repository are involved (JavaScript/TypeScript, Python, Rust).

## Inputs

- Optional list of relevant manifests/lockfiles present in the repository.
- Installed tooling for any ecosystem being updated.
- Existing Dependabot PR list for final reconciliation.

## Version policy

- Prefer `major.minor` constraints when possible.
- Avoid patch pins unless required; if required, document the reason and use explicit ranges like `>=X.Y.Z,<X.(Y+1)`.
- For `0.x` dependencies, prefer minor-capped ranges (`X.Y.*` semantics; use exact `==X.Y.*` when expressing a PEP 508 string).
- Never edit lockfiles by hand; regenerate them with the ecosystem tool.
- For npm semver, `1.2` is shorthand for `>=1.2.0 <1.3.0`.

## Hard gates (non-negotiable)

- Do not hand-edit lockfiles. Regenerate them with the ecosystem tooling.
- Do not proceed to Dependabot reconciliation until verification has run for the touched ecosystems.
- If verification fails, stop and report the failure; do not "fix forward" by stacking unrelated changes.

## Procedure (repo-agnostic)

1. Inventory applicable ecosystems by checking for files:
    - JavaScript/TypeScript: `package.json` and `pnpm-lock.yaml` (if present)
    - Python: `pyproject.toml` and `poetry.lock` (if present)
    - Rust: `Cargo.toml` and `Cargo.lock` (if present)
      Only run commands and edit files for ecosystems that exist.

2. Update manifests first.
    - Normalize and bump constraints in each relevant manifest before touching lockfiles.
    - Keep JS and Rust requirements at `major.minor` whenever practical (exceptions require explicit patch-pin rationale).
    - For `pnpm`:
        - Run `pnpm -r outdated` first.
    - For `Poetry`:
        - Run `poetry show --outdated --top-level` first.
    - For `Cargo`:
        - Keep root and workspace entries at `major.minor` unless pinning is required.
    - If manifests use Poetry version operators and the package is in `0.x`, normalize to `X.Y.*` (or `==X.Y.*` in PEP 508 strings).
    - If manifests use Poetry version operators and the package is `>=1.0`, normalize to `~=X.Y`.
    - For lockfile updates without manifest changes, skip dependency regeneration commands and run the appropriate non-updating lock-sync path.

3. Regenerate lockfiles.
    - Update manifests first, then lockfiles (unless a no-change lockfile sync is required).
    - Use the ecosystem lockfile commands:
        - `pnpm -w install` (or `pnpm -w update` when manifest ranges are unchanged)
        - `poetry update --with dev`
        - `cargo update -w`
    - If lockfiles require sync because an additional lockfile format is present, run:
        - `npm install --package-lock-only` (when `package-lock.json` exists).
    - For Cargo, if updates do not apply, run `cargo update -w --verbose` and record the likely blocker (for example: toolchain or MSRV compatibility).

4. Verify.
    - Run stack-relevant checks: linters, tests, and any repository-level validation scripts.
    - Re-run package-manager stale checks (`pnpm -r outdated`, `poetry show --outdated --top-level`) where those ecosystems were edited.
    - Capture evidence for what changed and what remains outdated.

5. Reconcile Dependabot PRs last.
    - Re-check open Dependabot PRs first by list (`gh pr list --state open --search "author:app/dependabot"`).
    - Classify each open PR as: covered by this change, blocked by constraints, or intentionally deferred.
    - If intentionally deferred, document the reason clearly in release/dependency notes.
    - If a dependency is intentionally capped but still noisy, either upgrade the capped line or add a documented `.github/dependabot.yml` ignore rule.

If your repo uses Cargo workspace dependencies:

- In root `Cargo.toml`, normalize workspace dependency entries to inline table form with an explicit `version` key.
- In member `Cargo.toml` files, set `workspace = true` and omit both `version` and `path`.
- Group dependencies by origin and separate each group with a single blank line.

## Outputs

- List each manifest and lockfile changed (with file paths).
- Provide commands run per ecosystem and outcome (updated, no-op, or blocked).
- Summarize remaining update signal with classification for each remaining PR (`covered`, `blocked`, or `intentionally deferred`).
- Call out any unresolved blockers (including version constraints, test/lint failures, or toolchain compatibility).

## Verification template

- Confirm manifest updates were applied before lockfile regeneration.
- Confirm lockfiles regenerated by tooling only.
- Confirm verification tasks ran for each touched ecosystem and include the exact commands.
- Confirm Dependabot status aligns with manifest state.

## Quick reference

- Detect ecosystems: `package.json`, `pyproject.toml`, `Cargo.toml`.
- Pre-checks:
  - `pnpm -r outdated`
  - `poetry show --outdated --top-level`
- Lockfiles (never hand-edit):
  - `pnpm -w install` / `pnpm -w update`
  - `poetry update --with dev`
  - `cargo update -w`
- Reconcile Dependabot last: `gh pr list --state open --search "author:app/dependabot"`.

## Common mistakes

- Editing lockfiles by hand instead of regenerating.
- Mixing ecosystems in one verification step (run verification for each touched stack).
- Reconciling Dependabot before manifests/lockfiles are consistent.
- Stacking “fix forward” unrelated changes after a verify failure (stop and report instead).
