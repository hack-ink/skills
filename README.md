# hack.ink AI-agent skills

This repository hosts reusable agent skills for Codex workflows.

## Available skills

- `sidecars` - sidecar fan-out guidance for one task, with a main-thread-first model and read-only `scout`/`skeptic` sidecars (`sidecars/SKILL.md`).
- `dep-roll` - latest-compatible dependency-graph upgrade workflow for pnpm, Poetry, and Cargo, with X.Y manifest-range discipline, tooling-owned lock regeneration, verification, and trailing Dependabot reconciliation (`dep-roll/SKILL.md`).
- `python-policy` - Python policy for runtime boundaries and project-configured quality gates, deferring to checked-in bootstrap and allowing documented isolated runtimes when required (`python-policy/SKILL.md`).
- `research` - research/investigation workflow that reads existing materials, clarifies unknowns with the user, and makes evidence-backed recommendations with websearch (`research/SKILL.md`).
- `research-pro` - consult ChatGPT Pro via chatgpt.com Projects for architecture/research decisions, with Pro thinking defaulting to Extended (use Standard/default only when requested), project-only memory set only when creating a new Project, and polling-aware handoff (`research-pro/SKILL.md`).
- `scrapling` - fallback web-scraping workflow for Scrapling when `curl`, built-in web fetch, or web search tools return incomplete, JS-shell, or bot-blocked content, with static/dynamic/stealth mode selection and CLI/Python/MCP examples (`scrapling/SKILL.md`).
- `rust-policy` - Rust policy for scope, toolchain/workflow, safety, formatting, error handling, logging, and ownership, with `rustfmt` as the final formatting authority (`rust-policy/SKILL.md`).
- `git-worktrees` - worktree setup and lifecycle guidance for isolated branches, independent parallel lanes, safe directory selection, and repo-native bootstrap (`git-worktrees/SKILL.md`).
- `parallel-conflict-resolution` - conflict triage and reconciliation workflow for merge/rebase/cherry-pick collisions across worktrees or independent branches (`parallel-conflict-resolution/SKILL.md`).
- `skill-routing` - generic skill-discovery and loading policy with an optional manual child denylist; the shipped policy uses version 5 with `child_forbidden = ["sidecars"]` and accepts only known local skill names as explicit restrictions (`skill-routing/SKILL.md`).
- `plan-writing` - producer stage of the shared machine-first planning contract: creates or revises persisted `plan/1` files under `docs/plans/YYYY-MM-DD_<feature-name>.md` and owns strategy, task graph, defaults, and replanning policy (`plan-writing/SKILL.md`).
- `plan-execution` - consumer stage of the shared machine-first planning contract: reads saved `plan/1` files, advances only runtime state, and blocks on missing or invalid saved authority instead of inferring execution intent from chat (`plan-execution/SKILL.md`).
- `delivery-prepare` - producer stage of the shared machine-first delivery contract: local delivery checks plus a valid `delivery/1` payload with explicit authority, mode, and typed refs for downstream closeout (`delivery-prepare/SKILL.md`).
- `delivery-closeout` - consumer stage of the shared machine-first delivery contract: reads the latest pushed `delivery/1` payload, treats Linear as the source of truth, and mirrors issue outcomes back to GitHub with comment plus open/close only (`delivery-closeout/SKILL.md`).
- `codebase-review` - methodology and tooling for full codebase review with risk triage, slicing, findings, decision logs, and SHA-anchored coverage gates (`codebase-review/SKILL.md`).

## Contributing

To add or update a skill:

1. Create a new `<skill-name>/SKILL.md` with required frontmatter (`name`, `description`).
2. Keep installable runtime assets with the skill itself. If `SKILL.md` references a script, template, schema, or helper at runtime, keep it under `<skill-name>/`.
3. Keep repo-local validation assets under `dev/<skill-name>/`. Smoke tests, e2e fixtures, backtests, and maintainer-only validation entrypoints belong there and are not part of the installed skill contract.
4. Treat generated artifacts, lockfiles, codegen outputs, and build outputs as tooling-owned. Skills must not instruct manual edits to those files when a canonical regeneration or sync command exists; they should point to the canonical command and verify the regenerated result instead.
5. Keep instructions concise, testable, and narrowly scoped.
6. Update this `README.md` catalog when new skills are added.

## Repository layout

- This repo intentionally ships **skills only**.
- Routing/push policy (if any) should live in your Codex home configuration (outside this repo).
- `<skill-name>/SKILL.md` - required skill definition.
- `<skill-name>/...` - installable runtime assets referenced by `SKILL.md` (scripts, templates, schemas, references).
- `dev/<skill-name>/...` - repo-local smoke tests and maintainer validation helpers; these are not part of the installed skill contract.
