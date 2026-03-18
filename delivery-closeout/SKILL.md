---
name: delivery-closeout
description: 'Use when closing out or syncing delivery state after a push, especially for requests like "ship this", "close out the issue", "sync trackers", "tracker sync", or "update Linear/GitHub issues". Consumes a pushed anchor plus an explicit machine-first `delivery/1` contract produced by `delivery-prepare`, whether the contract lives on that anchor commit or is supplied separately via stdin/file, and mirrors Linear issue outcomes back to GitHub issues with comment plus open/close only.'
---

# Delivery Closeout

## Objective

Consume a pushed anchor plus a valid `delivery/1` contract and sync delivery state
back to Linear and GitHub.

## Scope

- This is an explicit workflow skill, not a real git hook.
- This skill is the consumer stage of the shared delivery contract.
- V1 mutates issues only.
- Linear is authoritative for internal workflow state.
- GitHub mirrors Linear via comment plus open/close only.
- Branch names, PR URLs, and chat wording are evidence/backlinks only. They do not replace the `delivery/1` contract.
- If the reviewed code anchor should remain unchanged, provide the final closeout contract separately via stdin or file instead of creating an empty follow-up commit just to flip `delivery_mode`.

## Required inputs

- A pushed commit that is ready to use as the closeout anchor.
- A valid `delivery/1` contract produced by `delivery-prepare`.
- When the final contract is not stored on the anchor commit itself, both an explicit anchor rev and an explicit contract source:
  - `ANCHOR_REV=<pushed sha>`
  - `--stdin`
  - `--contract-file <path>`
- Access to native Linear MCP plus GitHub CLI/API.
- The skill root path so the helper can run:
  - `DELIVERY_CLOSEOUT_HOME=<skill root containing this SKILL.md>`

## Hard gates

- Do not widen this skill into GitHub Projects, milestones, label governance, or PR lifecycle changes.
- If the current branch has no upstream, or `HEAD` does not equal `@{u}`, block sync.
- If the contract source is stdin or `--contract-file`, require `--anchor-rev`. Do not accept a detached contract without a pushed anchor.
- If an explicit anchor rev is used, require that anchor to already be reachable from `@{u}`. Do not close out an unpushed or orphaned commit.
- If `scripts/read_delivery_contract.py` reports invalid `delivery/1`, stop before any tracker mutation.
- The contract may omit Linear refs entirely for untracked work.
- Linear related refs without a Linear authority ref are invalid and must block closeout.
- If the contract declares no Linear refs at all, treat the delivery as untracked: do not mutate Linear or GitHub, and emit skipped tracker rows.
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

1. Confirm the pushed context and anchor.
   - Run:
     - `git rev-parse --abbrev-ref HEAD`
     - `git rev-parse --abbrev-ref --symbolic-full-name @{u}`
     - `git rev-parse HEAD`
     - `git rev-parse @{u}`
   - Require `HEAD == @{u}`. If not, block closeout because the pushed context is ambiguous.
   - Set `ANCHOR_REV=HEAD` by default.
   - If you are closing out an older reviewed commit, set `ANCHOR_REV=<sha>` explicitly and verify it is already pushed:
     - `git rev-parse "$ANCHOR_REV"`
     - `git merge-base --is-ancestor "$ANCHOR_REV" @{u}`
   - Block closeout if the anchor rev is missing or not reachable from `@{u}`.
2. Read and validate the `delivery/1` contract.
   - When the contract already lives on the anchor commit, run:
     - `python3 "$DELIVERY_CLOSEOUT_HOME/scripts/read_delivery_contract.py" --rev "$ANCHOR_REV"`
   - When the final closeout contract is supplied explicitly over stdin, run:
     - `python3 "$DELIVERY_CLOSEOUT_HOME/scripts/read_delivery_contract.py" --anchor-rev "$ANCHOR_REV" --stdin`
   - When the final closeout contract is supplied from a file, run:
     - `python3 "$DELIVERY_CLOSEOUT_HOME/scripts/read_delivery_contract.py" --anchor-rev "$ANCHOR_REV" --contract-file "$CONTRACT_FILE"`
   - The helper validates:
     - `authority == linear`
     - `delivery_mode` is explicit
     - `refs` are typed objects
     - at most one Linear authority ref exists
     - any Linear related refs require that authority ref
   - The helper returns the resolved anchor commit SHA even when the contract comes from stdin or a file.
   - Treat any validation error as a sync blocker.
3. Build the sync set.
   - Extract the authoritative Linear issue from `authority_ref` when it exists.
   - Extract any additional Linear refs from `related_linear_refs`.
   - Extract GitHub mirror targets from `github_mirror_refs`.
   - Keep one report row per typed ref.
   - Preserve optional evidence backlinks such as branch name, anchor commit URL, and PR URL.
4. Read current tracker state before mutating.
   - Linear:
     - `get_issue` for each internal issue
     - `list_issue_statuses` for the issue team when a state transition is needed
   - GitHub:
     - `gh issue view <number> --repo <owner/repo> --json number,state,title,url`
   - Prefer native Linear MCP for normal issue reads and writes. Fall back only if MCP lacks the required surface.
5. Decide the authoritative Linear outcome.
   - Use `delivery_mode` from the contract:
     - no authority ref:
       - Leave Linear and GitHub unchanged in v1.
       - Emit skipped tracker rows only when the contract declares no Linear refs at all.
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
   - If no authority ref was declared, skip this step.
7. Mirror the authoritative Linear outcome to GitHub.
   - Only mirror GitHub refs when an authority Linear ref exists.
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
- contract source: <git|stdin|file>
- mode: <closeout|status-only|reopen>

Refs
- contract: `python3 "$DELIVERY_CLOSEOUT_HOME/scripts/read_delivery_contract.py" ...` (exit: <code>)
- authority: <linear issue id | none>
- related linear refs: <count>
- GitHub mirrors: <count>

Tracker rows
- <ref> -> <system> -> intended: <action> -> result: <applied|skipped|warned|blocked>

Warnings
- <warning text>

Blocked
- <blocked text>
```
