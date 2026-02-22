# hack.ink AI-agent skills

This repository hosts reusable agent skills for Codex workflows.

## Available skills

- `codex-multi-agent-protocol` — canonical 4-role protocol package with Director/Auditor/Orchestrator/Implementer schemas and test methodology (`codex-multi-agent-protocol/SKILL.md`).
- `dep-roll` — controlled dependency-upgrade workflow for pnpm, Poetry, Cargo, verification, and Dependabot alignment (`dep-roll/SKILL.md`).
- `python-style` — mandatory Python conventions for shared workspace virtualenv setup and Poetry workflow (`python-style/SKILL.md`).
- `research` — research/investigation workflow that reads existing materials, clarifies unknowns with the user, and makes evidence-backed recommendations with websearch (`research/SKILL.md`).
- `rust-style` — mandatory Rust conventions for scope, toolchain/workflow, safety, formatting, error handling, logging, and ownership (`rust-style/SKILL.md`).
- `pre-commit` — repository commit/push gate with repo-specific Makefile.toml task checks and workflow validation (`pre-commit/SKILL.md`).

## Contributing

To add or update a skill:

1. Copy `_template/SKILL.md` into your new skill folder as `<skill-name>/SKILL.md` and replace placeholders.
2. Keep instructions concise, testable, and narrowly scoped.
3. Update this `README.md` catalog when new skills are added.

## Repository policies

- **Commit messages**: use the `cmsg/1` single-line JSON format used throughout `git log`.
- **Language**: do not add CJK characters to tracked files.
- **Integration**: prefer PR + merge queue and avoid bypassing branch protection or force-pushing.

## Repository layout

- `AGENTS.md` — repository-specific operating instructions.
- `<skill-name>/SKILL.md` — required skill definition.
