---
name: sidecars
description: Use when a task benefits from sidecar fan-out for exploration or critique while the main thread remains the only implementation owner.
---

# Sidecars

## Purpose

Use Codex sidecars as optional, read-only agents inside one task. This skill explains when to spawn sidecars, when not to, and how to ask for evidence that the main thread can use immediately.

## Core model

- The main thread owns the task from start to finish.
- `scout` and `skeptic` are disposable sidecars.
- Sidecars are read-only. They must not edit repo content, delegate further, or take implementation ownership.
- If a sidecar concludes that code should change, it stops and hands that conclusion back to the main thread.

## Spawn a `scout` when

- You need codebase exploration, repo probing, reproductions, or evidence gathering in parallel.
- You need multiple independent research questions answered faster than one serial pass.
- You want a sidecar to gather evidence while the main thread continues direct work.

## Spawn a `skeptic` when

- You want an adversarial read on the current theory or planned change.
- You need someone to look for missed edge cases, missing tests, missing evidence, or regression risks.
- You want a read-only review pass before trusting a fix, explanation, or closeout claim.

## Do not spawn anything when

- A short local probe by the main thread will answer the question.
- The subtask would require repo edits or sustained implementation ownership.
- Two sidecars would duplicate the same objective.
- The output would not materially change the next main-thread step.

## One realistic use

- Suspected flaky test regression in one feature area:
  - Spawn a `scout` to inspect the failing paths, logs, or test output and decide whether the current theory has direct evidence.
  - Spawn a `skeptic` to challenge that theory and list alternative causes, missing tests, or missing evidence.
  - The main thread stays the only implementation owner, keeps working directly, and retires stale sidecars once enough evidence exists.

## Sidecar round

- Spawn one or more sidecars only when each sidecar has a distinct objective.
- Keep executing directly while sidecars run; do not stop just because a sidecar is still working.
- At the next decision boundary, do one bounded collect step.
- If a collect times out, treat that sidecar as not ready yet, not as an automatic failure.
- Retire a sidecar only when its missing evidence is already covered elsewhere or the main thread's acceptance is already independently satisfied.
- If a sidecar still holds the only missing evidence, do not retire it; do one more bounded collect step or spawn a narrower replacement sidecar.
- If enough evidence already exists, retire stale or redundant sidecars and continue direct execution.
- If evidence is still insufficient after the bounded collect step, start a narrower new round or mark the task blocked.

## Writing a good sidecar prompt

- Give the sidecar exactly one narrow objective.
- Point to the smallest relevant files, commands, or evidence sources.
- Ask for concrete findings, not open-ended brainstorming.
- Ask the sidecar to stop at evidence and recommended next checks, not implementation.
- Keep prompts short enough that the sidecar does not need to reconstruct the whole task.

Good `scout` prompt shape:

```text
Inspect <paths> and determine whether <specific claim> is true.
Return only the evidence, the confidence level, and the smallest next check if evidence is missing.
Do not edit files.
```

Good `skeptic` prompt shape:

```text
Challenge this theory: <current theory>.
Look for missing edge cases, contradictory evidence, or tests we would still need before trusting it.
Do not edit files.
```

## Concurrency rules

- Do not add a local cap beyond whatever the runtime already enforces.
- Every sidecar must have a distinct objective.
- Every sidecar's output must be consumable by the main thread.
- Once enough evidence exists, retire stale or redundant sidecars instead of waiting for them.

## Red flags

- Treating a sidecar as a code-writing lane
- Spawning sidecars with overlapping objectives
- Waiting on a stale sidecar that no longer affects the next decision
- Adding extra coordination machinery on top of the runtime

## Source-repo maintainer check

- When editing the owning skills repo rather than an installed copy, run `python3 dev/sidecars/run_smoke.py` from that repo root.
