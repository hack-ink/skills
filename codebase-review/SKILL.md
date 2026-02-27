---
name: codebase-review
description: Use for open-box review of medium/large codebases requiring full-breadth, risk-prioritized inspection.
---

# Codebase Review

## Purpose

This skill defines a repeatable codebase-wide review workflow for any language stack.
It combines risk triage, execution slicing, severity-driven findings, decision logs, and measurable review coverage.

## When to use

- Repository is large or fast-growing and file-by-file PR review is insufficient.
- You need predictable assurance before release or risky refactors.
- You need auditable review evidence tied to exact file revisions.
- You need an out-of-box process that scales across multiple paths and teams.

## Scope model

- Scope is explicit and repeatable.
- You can review all tracked files or constrain scope in exactly one mode:
  - Pass `--scope-file` for a frozen explicit file list.
  - Pass one or more `--pathspec` values for a dynamic git-based slice.
- If you need multiple scope files, merge them first (e.g., `cat a.txt b.txt > scope.txt`) and pass the merged file.
- Do not combine `--scope-file` and `--pathspec`; choose one mode per run.

## Open-box methodology

1. Set campaign boundaries
  - Freeze review scope as either all tracked files or explicit allowlists.
  - Record non-goals and hard exclusions up front.
  - Define exit criteria: coverage threshold, unresolved critical finding policy, and risk register completeness.
  - Initialize campaign artifacts under a stable folder such as `review/`.

2. Build risk register
  - Fill `risk-register-template.md` from domain knowledge and recent incidents.
  - Score each item by `impact` / `likelihood` / `exposure` on 1-5 scales.
  - Use a concise risk score formula:
    - `risk_score = impact × likelihood × exposure` (range 1-125).
    - `1-24 = Low`, `25-54 = Medium`, `55-94 = High`, `95-125 = Critical`.
  - Example:
    - Cross-tenant balance write path exposed externally: impact 5 × likelihood 4 × exposure 4 = 80 (High).
    - Internal utility crate refactor with low blast radius: impact 2 × likelihood 2 × exposure 2 = 8 (Low).
  - Tag boundaries: security trust, concurrency/state, IO/backing store, ownership, migration, and API compatibility.

3. Create slice plan
  - Translate risk ranking into ordered slices in `slice-plan-template.csv`.
  - Keep slice size bounded by owner capacity (recommended 300-500 LOC or one module).
  - Add `risk_score` + `reviewer` + `wip_state` to make triage and concurrency explicit.
  - Set a campaign WIP cap (`wip`) and require dependency order (`depends_on`) across slices.

4. Execute reviews + findings loop
  - Review files in slice order using language-specific and domain checks.
  - Record findings in `findings-backlog-template.csv` with severity and evidence.
  - For multi-reviewer campaigns, define one reviewer lead and multiple execution reviewers per slice:
    - Start high-risk slices first, then medium, then low.
    - Allow at most `wip` concurrent slices; no single reviewer owns more than one active high-risk slice.
    - Require independent review for High/Critical findings when possible.
  - Severity model:
    - Critical (optional CVSS 9.0-10.0): block merge by default, require immediate fix or explicit accepted risk.
    - High (optional CVSS 7.0-8.9): merge block until fixed or accepted risk is logged.
    - Medium (optional CVSS 4.0-6.9): require mitigation plan and owner deadline.
    - Low (optional CVSS 0.1-3.9): keep in backlog with scheduled cleanup.
    - Optional CVSS mapping is advisory; use local severity judgment when CVSS is unavailable.
  - Acceptance criteria:
    - No unresolved Critical on close.
    - No High with `triage_state` not equal to `fixed|verified|accepted_risk`.
    - Medium items without mitigation or due date are blockers.
    - Low items can remain open only with explicit backlog closure plan.
  - Re-review triggers:
    - Any reviewed file changes after its ledger row is created (SHA stale).
    - Severity is upgraded after triage or after mitigation review.
    - A finding enters `accepted_risk` state or enters/extends beyond its due date.
  - Re-check fixed points and stale slices.

5. Decision log
  - Capture tradeoffs and exceptions in `decision-log-template.md`.
  - Use ADR-style structure: context, decision drivers, options, decision, consequences, owner, and review evidence.
  - Link unresolved decisions to backlog items and scope entries.

6. Calibration and stop conditions
  - Default hard gate: `--min-coverage` must stay at 100 unless approved waiver.
  - A campaign can close only when:
    - all active slices have ledger rows,
    - all Critical and High are resolved or explicitly waived,
    - every high-risk register entry has an owner decision.

7. Coverage + forward gates
  - Run `check-review-coverage.py` regularly and before merge gates.
  - Coverage is per current blob SHA with status `approved` only.
  - Forward gates must block merges when scope files are stale or uncovered.
  - GitHub forward gates (copy/paste checklist):
    - [ ] Create/enable branch ruleset or branch protection for release and main branches.
    - [ ] Add CODEOWNERS and define ownership for high-risk paths (`/src/security/**`, `/migrations/**`, etc.).
    - [ ] Require pull request before merge.
    - [ ] Require at least one approving review.
    - [ ] Require code review approval from owners for paths with critical code ownership.
    - [ ] Enable `Dismiss stale pull request approvals when new commits are pushed`.
    - [ ] Require status checks to pass:
      - [ ] Code review coverage job (e.g., `python3 check-review-coverage.py --min-coverage 100`).
      - [ ] Security/static checks and relevant build/test pipelines.
    - [ ] Restrict bypass:
      - [ ] Turn off branch-bypass for non-admin/service roles.
      - [ ] Restrict bypass exceptions to explicit release service accounts only.
    - [ ] Add optional rulesets/rules for sensitive paths:
      - [ ] Add a ruleset condition for `/.*/` high-risk paths.
      - [ ] Require specific reviewers (or reviewer teams) on those paths.
      - [ ] Require additional required checks for those paths.
  - Branch protection mapping:
    - GitLab
      - [ ] Set approval rules and minimum approvers.
      - [ ] Add protected-branch merge restrictions and prevent force-push when needed.
      - [ ] Configure approver groups for sensitive file patterns where supported.
    - Azure DevOps
      - [ ] Turn on minimum reviewer policy and required approvals.
      - [ ] Require check-in policy checks and build validation.
      - [ ] Enable work item linking and auto-completion criteria.
    - Bitbucket
      - [ ] Add branch restrictions with minimum approvals.
      - [ ] Require successful build/status checks and merge checks.
      - [ ] Restrict push and merge rights for protected branches.

## Attestation rules

A file is covered only when:

- It is in campaign scope.
- Ledger status is `approved`.
- `blob_sha` matches the current revision hash.

`review coverage = approved_in_scope_files / total_in_scope_files`

This is review coverage, not test coverage.

## Evidence artifacts

- `ledger-template.csv`
- `notes-template.md`
- `risk-register-template.md`
- `slice-plan-template.csv`
- `findings-backlog-template.csv`
- `decision-log-template.md`
- `check-review-coverage.py`
- `forward-gates-template.md`

## Commands

```bash
SKILLS_HOME="${CODEX_HOME:-$HOME/.codex}/skills"
CODEBASE_REVIEW_HOME="$SKILLS_HOME/codebase-review"
```

- Initialize a reusable campaign layout in the target repo:

```bash
mkdir -p review
cp "$CODEBASE_REVIEW_HOME"/ledger-template.csv review/ledger.csv
cp "$CODEBASE_REVIEW_HOME"/risk-register-template.md review/risk-register.md
cp "$CODEBASE_REVIEW_HOME"/slice-plan-template.csv review/slice-plan.csv
cp "$CODEBASE_REVIEW_HOME"/findings-backlog-template.csv review/findings-backlog.csv
cp "$CODEBASE_REVIEW_HOME"/decision-log-template.md review/decision-log.md
cp "$CODEBASE_REVIEW_HOME"/forward-gates-template.md review/forward-gates.md
``` 

- Create initial Rust scope and run one-time scope snapshot:

```bash
git ls-files \
  -- '*.rs' 'src/**/*.rs' 'Cargo.toml' '*.toml' \
  | sort > review/scope-files.txt
```

- Campaign artifact layout (copy this shape):

```text
repo-root/
  review/
    scope-files.txt
    ledger.csv
    risk-register.md
    slice-plan.csv
    findings-backlog.csv
    decision-log.md
    notes/
```

- Check coverage with explicit scope file (ledger in target repo):

```bash
python3 "$CODEBASE_REVIEW_HOME"/check-review-coverage.py \
  --repo-root . \
  --scope-file review/scope-files.txt \
  --ledger review/ledger.csv \
  --min-coverage 100
```

- Check a Rust slice without frozen scope:

```bash
python3 "$CODEBASE_REVIEW_HOME"/check-review-coverage.py \
  --repo-root . \
  --pathspec '*.rs' \
  --ledger review/ledger.csv \
  --min-coverage 100
```

- Start with parallel reviewers then merge gating:

```bash
# 1) Reviewer workers run independently on slice windows and produce review notes:
python3 "$CODEBASE_REVIEW_HOME"/check-review-coverage.py --help

# 2) Integrator runs once after merge decisions are ready:
python3 "$CODEBASE_REVIEW_HOME"/check-review-coverage.py \
  --repo-root . \
  --scope-file review/scope-files.txt \
  --ledger review/ledger.csv \
  --min-coverage 100
```

## References

- [Google Software Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
- [OWASP Secure Code Review Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Code_Review_Cheat_Sheet.html)
- [NIST SSDF](https://csrc.nist.gov/projects/ssdf) and [NIST Risk Management Guide](https://www.nist.gov/publications/guide-conducting-risk-assessments)
- [GitHub CODEOWNERS](https://docs.github.com/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [GitHub required reviewer rule](https://github.blog/changelog/2026-02-17-required-reviewer-rule-is-now-generally-available/)
- [GitHub branch rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
- [Documenting Architecture Decisions (Cognitect)](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [AWS ADR Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/welcome.html)
- [Microsoft ADR guidance](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record)
- [MADR ADR format](https://adr.github.io/madr/)
- [FIRST CVSS v3.1](https://www.first.org/cvss/v3-1/specification-document)
- [OWASP Risk Rating Methodology](https://owasp.org/www-community/OWASP_Risk_Rating_Methodology)
- [Chromium severity guidelines](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/security/severity-guidelines.md)
- [GitHub code scanning alert lifecycle](https://docs.github.com/en/code-security/how-tos/manage-security-alerts/manage-code-scanning-alerts/resolving-code-scanning-alerts)
- [GitLab approvals](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/)
- [GitLab protected branches](https://docs.gitlab.com/ee/user/project/protected_branches/)
- [Azure DevOps branch policies](https://learn.microsoft.com/en-us/azure/devops/repos/git/branch-policies)
- [Bitbucket branch permissions/restrictions](https://support.atlassian.com/bitbucket-cloud/docs/branch-permissions/)

## Common mistakes

- Changing scope after execution start and claiming continuity.
- Using file touch history as review evidence.
- Marking files covered with non-approved status.
- Allowing stale SHA rows to remain active.
- Closing Critical or High findings without a decision record.
