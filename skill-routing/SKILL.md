---
name: skill-routing
description: Use at the start of a task, before clarifying questions, or before taking action whenever one or more installed skills might apply. Establishes how to discover relevant skills, load them using the current runtime's mechanism, and follow them before proceeding.
---

# Skill Routing

## Core rule

- Check for relevant or explicitly requested skills before any response or action.
- Treat explicit requests and implicit matches the same way. A skill does not need to be named verbatim to apply.
- If a skill has any credible chance of applying, inspect its routing surface first (`name`, `description`, and any runtime-exposed metadata), then load the selected skill before proceeding.
- Do not rely on memory of a skill. Load the current version because skills evolve.
- If a loaded skill turns out not to apply, drop it and continue. A false positive is acceptable; skipping a relevant skill is not.

## Path conventions

- All paths in this skill are relative to the skill root (the directory that contains this `SKILL.md`).
- The child skill policy file is `child-skill-policy.toml`.
- The policy script is `scripts/build_child_skill_policy.py`.

## Runtime contract

- Use the current runtime's supported skill-loading mechanism.
- If the runtime exposes a dedicated skill command or tool, use it.
- If skills are filesystem-backed, open the canonical skill entrypoint for that runtime, usually `SKILL.md`.
- Do not hardcode vendor-specific behavior or assume one loader exists everywhere.
- If a referenced skill cannot be loaded, say so briefly and continue with the best fallback.

## Child skill policy

- Child agents may still use skill discovery.
- When the current agent is a child, resolve the denylist from `child-skill-policy.toml`.
- The shipped policy file uses the version-5 neutral denylist shape.
- This denylist is intentionally minimal. It is not a full capability sandbox.
- `child_forbidden` is the only restriction field in this format.
- If the policy file omits a skill, child agents may use it when relevant.
- The denylist exists to block known local control-plane recursion or other explicitly forbidden local skills.
- Unknown installed skills are bounded by runtime child behavior rules, not by enumerating every name here.
- Policy entries must use known local skill names from this repo's installable skill catalog.
- Skills listed in `child_forbidden` must never be self-initiated by a child.
- There is no dispatch-level skill grant list in this source-repo design.

## Policy lifecycle

- The shipped policy file is initialized with only `sidecars` forbidden by default.
- There is no automatic bootstrap or proactive filling.
- Users fill the policy manually if they want restrictions.
- Users may also ask an agent to edit the policy file for them.
- `scripts/build_child_skill_policy.py` initializes or canonicalizes the policy file but does not classify or populate skills.
- The policy script rejects unknown skill names and legacy keys such as `main_thread_only`.
- If the user wants to rewrite the canonical shipped template, rerun:
  - `python3 scripts/build_child_skill_policy.py --write`

## Progressive disclosure

- Treat skill metadata as the routing layer and the skill body as the execution layer.
- Load only the skills that plausibly match the task; do not bulk-load every available skill "just in case."
- Load scripts, references, and assets only when the selected skill directs you to them or the task requires them.
- Keep context tight. Prefer the minimal set of skills that fully covers the task.

## Selection order

1. Load process skills first. These determine how to approach the task.
2. Load implementation or domain skills second. These determine how to execute within the chosen process.
3. If multiple skills overlap, prefer the smallest set with the clearest boundaries.
4. When the current agent is a child, apply any explicit restrictions from the child skill policy before selecting a restricted skill.

Examples:

- "Fix this bug" -> load debugging workflow skills before language- or framework-specific skills.
- "I have two unrelated implementation tasks in the same repo" -> isolate them before proceeding so each task has its own execution stream.
- "Write the implementation plan" or a task already running in Plan mode -> load the planning workflow before any code changes.
- "Execute this plan" or "continue from `docs/plans/...`" -> load the workflow that treats the saved plan as the execution entrypoint.
- "Build a React dashboard" -> load the smallest set of process and implementation skills that match the task.
- "This merge/rebase/cherry-pick conflict came from parallel branches or worktrees" -> load the workflow that resolves cross-branch conflicts.
- "Prepare a commit" -> load the commit/push gate before committing or pushing.

## Follow-through

- Announce which skill or skills you are using and why in one short line.
- If a skill includes a checklist, convert it into explicit tracked steps before execution.
- Follow rigid skills exactly. Adapt flexible skills only within their stated boundaries.
- Respect higher-priority instructions. System, developer, user, and repository guidance override a skill when they conflict.

## Authoring note

- When creating or updating skills, put trigger conditions and boundaries in the frontmatter `description`, because routing depends on it.
- Keep the skill body procedural and concise. Move detailed references into `references/` and deterministic scripts into `scripts/` only when needed.
