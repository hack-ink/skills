# hack.ink AI-agent skills

This repository hosts reusable agent skills for Codex workflows.

## Available skills

- `multi-agent` - canonical 5-role protocol package with Main (Director)/Auditor/Orchestrator/Coder/Operator schemas and test methodology (`multi-agent/SKILL.md`).
- `dep-roll` - controlled dependency-upgrade workflow for pnpm, Poetry, Cargo, verification, and Dependabot alignment (`dep-roll/SKILL.md`).
- `python-style` - mandatory Python conventions for shared workspace virtualenv setup and Poetry workflow (`python-style/SKILL.md`).
- `research` - research/investigation workflow that reads existing materials, clarifies unknowns with the user, and makes evidence-backed recommendations with websearch (`research/SKILL.md`).
- `rust-style` - mandatory Rust conventions for scope, toolchain/workflow, safety, formatting, error handling, logging, and ownership (`rust-style/SKILL.md`).
- `pre-commit` - repository commit/push gate with repo-specific Makefile.toml task checks and workflow validation (`pre-commit/SKILL.md`).
- `codebase-review` - methodology and tooling for full codebase review with risk triage, slicing, findings, decision logs, and SHA-anchored coverage gates (`codebase-review/SKILL.md`).

## Contributing

To add or update a skill:

1. Create a new `<skill-name>/SKILL.md` with required frontmatter (`name`, `description`).
2. Keep instructions concise, testable, and narrowly scoped.
3. Update this `README.md` catalog when new skills are added.

## Repository layout

- This repo intentionally ships **skills only**.
- Routing/push policy (if any) should live in your Codex home configuration (outside this repo).
- `<skill-name>/SKILL.md` - required skill definition.
