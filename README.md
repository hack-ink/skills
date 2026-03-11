# hack.ink AI-agent skills

This repository hosts reusable agent skills for Codex workflows.

## Available skills

- `multi-agent` - brokered two-state execution for one task or one PR-sized change stream, with schema-validated worker contracts and ownership locks (`multi-agent/SKILL.md`).
- `dep-roll` - latest-compatible dependency-graph upgrade workflow for pnpm, Poetry, and Cargo, with X.Y manifest-range discipline, tooling-owned lock regeneration, verification, and trailing Dependabot reconciliation (`dep-roll/SKILL.md`).
- `python-policy` - Python policy for runtime boundaries and project-configured quality gates, deferring to checked-in bootstrap and allowing documented isolated runtimes when required (`python-policy/SKILL.md`).
- `research` - research/investigation workflow that reads existing materials, clarifies unknowns with the user, and makes evidence-backed recommendations with websearch (`research/SKILL.md`).
- `research-pro` - consult ChatGPT Pro via chatgpt.com Projects for architecture/research decisions, with Pro thinking defaulting to Extended (use Standard/default only when requested), project-only memory set only when creating a new Project, and polling-aware handoff (`research-pro/SKILL.md`).
- `scrapling` - fallback web-scraping workflow for Scrapling when `curl`, built-in web fetch, or web search tools return incomplete, JS-shell, or bot-blocked content, with static/dynamic/stealth mode selection and CLI/Python/MCP examples (`scrapling/SKILL.md`).
- `rust-policy` - Rust policy for scope, toolchain/workflow, safety, formatting, error handling, logging, and ownership, with `rustfmt` as the final formatting authority (`rust-policy/SKILL.md`).
- `git-worktrees` - worktree setup and lifecycle guidance for isolated branches, independent parallel lanes, safe directory selection, and repo-native bootstrap (`git-worktrees/SKILL.md`).
- `parallel-conflict-resolution` - conflict triage and reconciliation workflow for merge/rebase/cherry-pick collisions across worktrees or independent branches (`parallel-conflict-resolution/SKILL.md`).
- `skill-routing` - generic skill-discovery and loading policy with an optional manual child-skill policy file; the shipped policy stays empty, keeps `default_child_policy = "any-agent"`, accepts only known local skill names as explicit restrictions, and uses `authorized_skills` only for skills manually marked `dispatch-authorized` (`skill-routing/SKILL.md`).
- `plan-writing` - plan-writing workflow for multi-step or risky tasks, including Plan mode handoff, evidence-grounded task decomposition, and durable plan docs using the `docs/plans/YYYY-MM-DD_<feature-name>.md` convention (`plan-writing/SKILL.md`).
- `plan-execution` - execution workflow for saved implementation plans, with critical plan review, checkpoint-based batches, repo-native verification, and staged progress reporting (`plan-execution/SKILL.md`).
- `pre-commit` - repository commit/push gate with repo-specific Makefile.toml task checks and workflow validation (`pre-commit/SKILL.md`).
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
- `dev/<skill-name>/...` - repo-local smoke/e2e/backtests for maintainers; these are validation helpers, not part of the installed skill contract.
