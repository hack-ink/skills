# Forward Gates Checklist Template

- [ ] Campaign scope is frozen and reviewed against the target branch.
- [ ] `check-review-coverage.py --min-coverage 100` is required in merge checks.
- [ ] CODEOWNERS covers all trust-sensitive directories.
- [ ] PRs require at least one approval before merge.
- [ ] Approval stale-dismissal is enabled.
- [ ] Bypass is restricted to named automation/release identities only.
- [ ] Sensitive paths have extra reviewer constraints.
- [ ] Critical/High decisions include ADR-backed acceptance when unresolved.

