---
name: scout-skeptic
description: "Use after a short local probe when a non-trivial task still has multiple files, plausible causes, or verification risks. Run a scout/skeptic checkpoint to gather evidence and challenge the current theory; use threshold-based read-only scout/skeptic child-agent fanout only when the probe still leaves multiple independent read-only questions, otherwise run the checkpoint locally while the main thread keeps implementation ownership."
---

# Scout-Skeptic

## Purpose

Use the `scout-skeptic` skill as an additive overlay for one task when a short local probe is not enough and the main thread would benefit from a bounded scout/skeptic checkpoint for evidence gathering or critique.

## Non-trivial threshold

Treat the task as trivial when the first short probe leaves only one obvious local action and no second independent verification or review question that could still change the next step.

Treat the task as non-trivial when the first short probe still leaves either of these:

- at least two independent read-only questions, hypotheses, or evidence gaps
- one remaining implementation path plus a second distinct verification, regression, or reviewer-risk question that could still change the next action

If unsure, write the local checkpoint explicitly and use that record to justify whether this skill should load.

## When this should be loaded

- Load this after the first short probe for non-trivial tasks when multiple files, questions, or evidence sources can be inspected in parallel.
- Load this when there are multiple plausible hypotheses, regression risks, or missing tests worth challenging before implementation or closeout.
- Load this when isolating exploration from the main context would reduce context bloat.
- If read-only child-agent execution is unavailable or unnecessary, still run the scout/skeptic checkpoint locally instead of skipping it.
- This skill commonly stacks with `systematic-debugging`, `research`, and `verification-before-completion`.
- Do not skip `scout-skeptic` solely because another process skill already applies.

## Core model

- The main thread owns the task from start to finish.
- `scout` and `skeptic` are read-only checkpoint roles.
- Use child-agent fanout as a thresholded mechanism, not a vague preference.
- When the fanout threshold is met, dispatch narrow read-only child-agent objectives.
- When child agents are unnecessary or unavailable, run the same scout/skeptic passes locally in the main thread.
- They must not edit repo content, delegate further, or take implementation ownership.
- If either pass concludes that code should change, hand that conclusion back to the main thread.

## Fanout threshold

Spawn child-agent objectives only when all of these are true after the first short probe:

- At least two independent read-only questions, hypotheses, or evidence gaps remain.
- Each question can be phrased as one narrow objective whose output would change the next main-thread decision.
- The objectives do not overlap, and one can be framed as `scout` evidence gathering while another can be framed as `skeptic` critique.
- The main thread still has direct work, synthesis, or another verification step to do while the child agents run.

Default first round shape when the threshold is met:

- Spawn one `scout` objective and one `skeptic` objective.
- Keep each objective narrow enough that the child agent does not need to reconstruct the whole task.

## Use a `scout` pass when

- You need codebase exploration, repo probing, reproductions, or evidence gathering in parallel.
- You need multiple independent research questions answered faster than one serial pass.
- You want a read-only evidence-gathering pass while the main thread continues direct work.

## Use a `skeptic` pass when

- You want an adversarial read on the current theory or planned change.
- You need someone to look for missed edge cases, missing tests, missing evidence, or regression risks.
- You want a read-only review pass before trusting a fix, explanation, or closeout claim.

Do not spawn child-agent objectives when any of these are true:

- A short local probe by the main thread will answer the question.
- Only one blocking read-only question remains.
- The subtask would require repo edits or sustained implementation ownership.
- The main thread would mostly wait on the result instead of continuing direct work or synthesis.
- The output would not materially change the next main-thread step.
- The objectives would duplicate each other or would not materially change the next decision.

## One realistic use

- Suspected flaky test regression in one feature area:
  - Run a `scout` pass to inspect the failing paths, logs, or test output and decide whether the current theory has direct evidence.
  - Run a `skeptic` pass to challenge that theory and list alternative causes, missing tests, or missing evidence.
  - If the first probe still leaves at least two independent read-only questions, dispatch those passes as separate read-only child-agent objectives; otherwise do them locally in sequence.
  - The main thread stays the only implementation owner and keeps working directly once enough evidence exists.

## Scout-Skeptic round

- Create child-agent objectives only when each one has a distinct objective.
- Keep executing directly while they run; do not stop just because one child agent is still working.
- At the next decision boundary, do one bounded collect step.
- If a collect times out, treat that child agent as not ready yet, not as an automatic failure.
- Retire a child agent only when its missing evidence is already covered elsewhere or the main thread's acceptance is already independently satisfied.
- If a child agent still holds the only missing evidence, do not retire it; do one more bounded collect step or dispatch a narrower replacement.
- If enough evidence already exists, retire stale or redundant child agents and continue direct execution.
- If evidence is still insufficient after the bounded collect step, start a narrower new round or mark the task blocked.

## Local checkpoint fallback

When child-agent fanout is unavailable, unnecessary, or below the threshold, run the checkpoint locally instead of skipping it.

When using the local fallback, say which threshold failed so the no-fanout decision is inspectable.

Treat the local checkpoint as complete only when you record all four items:

- current theory or working plan
- strongest contradictory evidence, regression risk, or skeptic concern
- missing evidence or missing test that would still change the decision
- next direct action the main thread will take

Keep this local checkpoint short and task-specific. It is a bounded reasoning artifact, not a second planning workflow.

## Writing a good prompt

- Give the child agent exactly one narrow objective.
- Point to the smallest relevant files, commands, or evidence sources.
- Ask for concrete findings, not open-ended brainstorming.
- Ask the child agent to stop at evidence and recommended next checks, not implementation.
- Keep prompts short enough that the child agent does not need to reconstruct the whole task.

Good `scout` child-agent prompt shape:

```text
Inspect <paths> and determine whether <specific claim> is true.
Return only the evidence, the confidence level, and the smallest next check if evidence is missing.
Do not edit files.
```

Good `skeptic` child-agent prompt shape:

```text
Challenge this theory: <current theory>.
Look for missing edge cases, contradictory evidence, or tests we would still need before trusting it.
Do not edit files.
```

## Concurrency rules

- Do not add a local cap beyond whatever the runtime already enforces.
- Every child-agent objective must have a distinct objective.
- Every child-agent output must be consumable by the main thread.
- Once enough evidence exists, retire stale or redundant child agents instead of waiting for them.

## Red flags

- Treating `scout` or `skeptic` as a code-writing lane
- Spawning overlapping child-agent objectives
- Waiting on a stale child agent that no longer affects the next decision
- Adding extra coordination machinery on top of the runtime
- Claiming a local checkpoint happened without recording the current theory, skeptic concern, missing evidence, and next direct action

## Source-repo maintainer check

- When editing the owning skills repo rather than an installed copy, run `python3 dev/scout-skeptic/run_smoke.py` from that repo root.
