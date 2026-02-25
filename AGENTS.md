# AGENTS.md - Skills Repo Guardrails

This repository ships skills that may be installed into Codex runtimes. Keep instructions explicit and fail-closed.

## Multi-agent spawn allowlist (hard gate)

If you are using the `codex-multi-agent-protocol` skill and the `dispatch-preflight.routing_decision == "multi_agent"`:

- Spawn ONLY protocol agent types (no built-ins/defaults).
- Do NOT spawn `worker`, `default`, `explorer`, or any other non-protocol agent type.
- If an unexpected agent type is spawned (or appears in logs/results), stop, close it, set `blocked=true`, and re-run using only protocol agent types.

Recommended protocol agent types:

- `auditor`
- `orchestrator`
- `operator`
- `coder_spark` (primary)
- `coder_codex` (availability fallback only)

## Protocol package changes

When modifying the protocol package (`codex-multi-agent-protocol/`), run:

- `python3 codex-multi-agent-protocol/references/e2e/run_smoke.py`

## Commits

- Before `git commit`/`git push`, run the repo `pre-commit` skill and use a `cmsg/1` JSON commit message.

