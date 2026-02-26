# AGENTS.md — skills repo routing gate

## Routing

- Route values (protocol schema): `single_agent`, `multi_agent`.
- Default to `single_agent` for tiny, clear, low-risk edits.
- Before any non-trivial action, record `t_max_s` (seconds) and `t_why`.
- If uncertain or estimated > 90 seconds, use `multi_agent`.

## Execution

- `single_agent`: Director executes directly and reports `t_max_s` + `t_why`.
- `multi_agent`: execute via the `multi-agent` skill. All spawn topology, allowlists, windowing, and evidence rules live under `multi-agent/`.

## Change control

- Do not edit unrelated content.
- If a conflict is detected, stop and report before proceeding.

## Push gate

- Before any `git push`, run the `pre-commit` skill.

