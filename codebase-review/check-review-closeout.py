#!/usr/bin/env python3
"""Validate review campaign closeout from machine-readable campaign artifacts."""

from __future__ import annotations

import argparse
import csv
import fnmatch
from pathlib import Path
from typing import Iterable, List


Row = dict[str, str]

RESOLVED_FINDING_STATES = {"fixed", "verified", "accepted_risk", "waived"}
ALLOWED_SLICE_STATES = {"planned", "active", "blocked", "done", "waived"}
ALLOWED_RISK_STATES = {"open", "in-review", "accepted", "mitigated", "waived"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check review campaign closeout from findings, slices, risk register, and ledger."
    )
    parser.add_argument("--repo-root", default=".", dest="repo_root")
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--findings", required=True)
    parser.add_argument("--slice-plan", required=True)
    parser.add_argument("--risk-register", required=True)
    return parser.parse_args()


def resolve_repo_path(base: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base / path


def load_csv(path: Path, required: Iterable[str], label: str) -> List[Row]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = [name for name in required if name not in fieldnames]
        if missing:
            raise SystemExit(f"{label} must include columns: {', '.join(missing)}")

        rows: List[Row] = []
        for row in reader:
            normalized = {key: (value or "").strip() for key, value in row.items()}
            primary = next(iter(required))
            if not normalized.get(primary) or normalized.get(primary, "").startswith("#"):
                continue
            rows.append(normalized)
        return rows


def load_ledger_files(path: Path) -> List[str]:
    rows = load_csv(path, ("reviewed_file", "blob_sha", "status"), "ledger")
    return [row["reviewed_file"] for row in rows]


def severity_rank(raw: str) -> str:
    return raw.strip().lower()


def triage_state(raw: str) -> str:
    return raw.strip().lower()


def parse_int(value: str, field: str, row_id: str, failures: List[str]) -> int | None:
    if not value:
        failures.append(f"{row_id}: missing {field}")
        return None
    try:
        return int(value)
    except ValueError:
        failures.append(f"{row_id}: invalid {field}={value!r}")
        return None


def check_findings(rows: List[Row], failures: List[str]) -> None:
    for row in rows:
        file_path = row["file"]
        row_id = f"finding:{file_path}:{row.get('signature') or row.get('line') or '?'}"
        severity = severity_rank(row["severity"])
        state = triage_state(row["triage_state"])

        if severity in {"critical", "high"} and state not in RESOLVED_FINDING_STATES:
            failures.append(f"{row_id}: unresolved {severity} finding with triage_state={state!r}")

        if severity == "medium" and state not in RESOLVED_FINDING_STATES:
            if not row.get("mitigation_plan"):
                failures.append(f"{row_id}: medium finding missing mitigation_plan")
            if not row.get("due_date"):
                failures.append(f"{row_id}: medium finding missing due_date")

        if state == "accepted_risk":
            for field in ("accepted_risk_reason", "accepted_risk_approver", "decision_ref"):
                if not row.get(field):
                    failures.append(f"{row_id}: accepted_risk missing {field}")


def split_scope_globs(raw: str) -> List[str]:
    values = [item.strip() for item in raw.replace(";", ",").split(",")]
    return [item for item in values if item]


def check_slice_plan(rows: List[Row], ledger_files: List[str], failures: List[str]) -> None:
    for row in rows:
        slice_id = row["slice_id"]
        state = row["wip_state"].strip().lower()
        if state not in ALLOWED_SLICE_STATES:
            failures.append(f"slice:{slice_id}: invalid wip_state={state!r}")
            continue

        if state == "active":
            patterns = split_scope_globs(row["scope_glob"])
            if not patterns:
                failures.append(f"slice:{slice_id}: active slice missing scope_glob")
                continue
            has_ledger_row = any(
                any(fnmatch.fnmatch(path, pattern) for pattern in patterns) for path in ledger_files
            )
            if not has_ledger_row:
                failures.append(f"slice:{slice_id}: active slice has no ledger rows in scope")


def risk_score(row: Row, row_id: str, failures: List[str]) -> int | None:
    if row.get("risk_score"):
        return parse_int(row["risk_score"], "risk_score", row_id, failures)

    impact = parse_int(row.get("impact", ""), "impact", row_id, failures)
    likelihood = parse_int(row.get("likelihood", ""), "likelihood", row_id, failures)
    exposure = parse_int(row.get("exposure", ""), "exposure", row_id, failures)
    if impact is None or likelihood is None or exposure is None:
        return None
    return impact * likelihood * exposure


def check_risk_register(rows: List[Row], failures: List[str]) -> None:
    for row in rows:
        risk_id = row["risk_id"]
        row_id = f"risk:{risk_id}"
        status = row["status"].strip().lower()
        if status not in ALLOWED_RISK_STATES:
            failures.append(f"{row_id}: invalid status={status!r}")
            continue

        score = risk_score(row, row_id, failures)
        if score is None or score < 55:
            continue

        if not row.get("owner"):
            failures.append(f"{row_id}: high-risk entry missing owner")
        if not row.get("decision_ref"):
            failures.append(f"{row_id}: high-risk entry missing decision_ref")
        if status not in {"accepted", "mitigated", "waived"}:
            failures.append(f"{row_id}: high-risk entry not closed (status={status!r})")


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    ledger_files = load_ledger_files(resolve_repo_path(repo_root, args.ledger))
    findings = load_csv(
        resolve_repo_path(repo_root, args.findings),
        ("file", "severity", "triage_state", "mitigation_plan", "due_date"),
        "findings backlog",
    )
    slice_plan = load_csv(
        resolve_repo_path(repo_root, args.slice_plan),
        ("slice_id", "scope_glob", "wip_state"),
        "slice plan",
    )
    risk_register = load_csv(
        resolve_repo_path(repo_root, args.risk_register),
        ("risk_id", "owner", "status", "impact", "likelihood", "exposure", "risk_score", "decision_ref"),
        "risk register",
    )

    failures: List[str] = []
    check_findings(findings, failures)
    check_slice_plan(slice_plan, ledger_files, failures)
    check_risk_register(risk_register, failures)

    print("Review closeout report")
    print(f"Findings rows: {len(findings)}")
    print(f"Slice rows: {len(slice_plan)}")
    print(f"Risk rows: {len(risk_register)}")
    print(f"Ledger rows: {len(ledger_files)}")

    if failures:
        print(f"Failures: {len(failures)}")
        for failure in failures[:50]:
            print(f"  FAIL {failure}")
        print("CLOSEOUT_FAIL")
        return 1

    print("Failures: 0")
    print("CLOSEOUT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
