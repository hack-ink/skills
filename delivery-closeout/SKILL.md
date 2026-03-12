---
name: delivery-closeout
description: 'Use when closing out or syncing delivery state after a push, especially for requests like "ship this", "close out the issue", "sync trackers", "tracker sync", or "update Linear/GitHub issues". Consumes the latest pushed machine-first `delivery/1` contract produced by `delivery-prepare`, using explicit authority, mode, and typed refs to mirror Linear issue outcomes back to GitHub issues with comment plus open/close only.'
---

# Delivery Closeout

## Objective

Consume the latest pushed `delivery/1` contract and sync delivery state back to Linear
and GitHub.

## Scope

- This is an explicit workflow skill, not a real git hook.
- This skill is the consumer stage of the shared delivery contract.
- V1 mutates issues only.
- Linear is authoritative for internal workflow state.
- GitHub mirrors Linear via comment plus open/close only.
- Branch names, PR URLs, and chat wording are evidence/backlinks only. They do not replace the `delivery/1` contract.

## Required inputs

- A pushed commit that is ready to use as the closeout anchor.
- A latest pushed commit carrying the `delivery/1` contract produced by `delivery-prepare`.
- Access to native Linear MCP plus GitHub CLI/API.
- The skill root path so the helper can run:
  - `DELIVERY_CLOSEOUT_HOME=<skill root containing this SKILL.md>`

## Hard gates

- Do not widen this skill into GitHub Projects, milestones, label governance, or PR lifecycle changes.
- If the current branch has no upstream, or `HEAD` does not equal `@{u}`, block sync. Use the pushed branch tip as the anchor, not an unpushed local commit.
- If `scripts/read_delivery_contract.py` reports invalid `delivery/1`, stop before any tracker mutation.
- The contract must contain exactly one Linear authority ref. GitHub-only ref sets are invalid because GitHub mirrors Linear rather than defining workflow state.
- Apply Linear mutations before GitHub mutations.
- If Linear mutation fails, stop and report `blocked`. Do not continue to GitHub.
- If GitHub write fails after Linear succeeded, report `warned`. Do not roll back Linear.
- Do not infer tracker linkage or closeout mode from branch names, PR titles, issue text, or user phrasing when a valid `delivery/1` contract is present.

## Contract-driven modes

- The contract's `delivery_mode` is authoritative.
- Supported modes:
  - `closeout`
  - `status-only`
  - `reopen`
- Do not override `delivery_mode` from chat wording when the contract is valid.

## Procedure

1. Confirm the pushed anchor.
   - Run:
     - `git rev-parse --abbrev-ref HEAD`
     - `git rev-parse --abbrev-ref --symbolic-full-name @{u}`
     - `git rev-parse HEAD`
     - `git rev-parse @{u}`
   - Require `HEAD == @{u}`. If not, block closeout because the latest pushed commit is ambiguous.
2. Read and validate the `delivery/1` contract.
   - Run:
     - `python3 "$DELIVERY_CLOSEOUT_HOME/scripts/read_delivery_contract.py"`
   - The helper validates:
     - `authority == linear`
     - `delivery_mode` is explicit
     - `refs` are typed objects
     - exactly one Linear authority ref exists
   - Treat any validation error as a sync blocker.
3. Build the sync set.
   - Extract the single authoritative Linear issue from `authority_ref`.
   - Extract any additional Linear refs from `related_linear_refs`.
   - Extract GitHub mirror targets from `github_mirror_refs`.
   - Keep one report row per typed ref.
   - Preserve optional evidence backlinks such as branch name, commit URL, and PR URL.
4. Read current tracker state before mutating.
   - Linear:
     - `get_issue` for each internal issue
     - `list_issue_statuses` for the issue team when a state transition is needed
   - GitHub:
     - `gh issue view <number> --repo <owner/repo> --json number,state,title,url`
   - Prefer native Linear MCP for normal issue reads and writes. Fall back only if MCP lacks the required surface.
5. Decide the authoritative Linear outcome.
   - Use `delivery_mode` from the contract:
     - `closeout`:
       - Move linked internal Linear issues to the team's completed state.
       - If there is exactly one completed state, use it.
       - If multiple completed states exist, prefer exact name `Done`.
       - If multiple completed states remain after that, block as ambiguous.
     - `status-only`:
       - Leave Linear unchanged in v1.
     - `reopen`:
       - Move the authority Linear issue to a non-terminal state.
       - Prefer exact name `In Progress`.
       - If `In Progress` is absent, prefer exact name `Backlog`.
       - If neither exists, block as ambiguous.
6. Apply Linear mutations first.
   - Record the resulting Linear state for each internal issue.
7. Mirror the authoritative Linear outcome to GitHub.
   - Always write a status comment that includes:
     - linked Linear issue id
     - resulting Linear state
     - anchor commit SHA or URL
     - PR URL if available
     - concise delivery summary
   - Only mirror GitHub refs declared in the contract with `role: "mirror"`.
   - If the authoritative Linear state is terminal, close the GitHub issue.
     - Prefer state `type` from the tool response when it is available.
     - If only the name is available, treat exact names `Done` and `Canceled` as terminal.
   - If the authoritative Linear state is non-terminal and the GitHub issue is closed, reopen it.
   - Otherwise keep the GitHub issue open.
8. Emit a final sync report.
   - Include the anchor commit, mode, contract result, one row per resolved ref, plus any warnings or blockers.

## Output

Produce a human-readable report with this shape:

```text
Delivery-closeout report

Anchor
- branch: <branch>
- upstream: <upstream>
- commit: <sha>
- mode: <closeout|status-only|reopen>

Refs
- contract: `python3 "$DELIVERY_CLOSEOUT_HOME/scripts/read_delivery_contract.py"` (exit: <code>)
- authority: <linear issue id>
- related linear refs: <count>
- GitHub mirrors: <count>

Tracker rows
- <ref> -> <system> -> intended: <action> -> result: <applied|skipped|warned|blocked>

Warnings
- <warning text>

Blocked
- <blocked text>
```
