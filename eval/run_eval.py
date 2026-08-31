"""
ITERATION 2 — eval-driven development for the LLM-judgment checks.

This is DELIBERATELY not a pytest test. Per the course material
(eval-driven development): distill LLM-judgment output to pass/fail
against a human-labeled golden set, log every row with its actual
findings/reasoning, and look at failures by hand before deciding the
check is good enough — not a single boolean assert that tells you
nothing about *why* it failed.

Run this after wiring a real LLM client into src/llm_checks/. It
writes a CSV to eval/results/ that you read like the spreadsheet the
course recommends starting with — module | expected | actual |
pass/fail | actual findings | notes.

USAGE:
    python eval/run_eval.py security_check
    python eval/run_eval.py duplicate_check
    python eval/run_eval.py all
"""
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

RESOURCE_TYPE_RE = re.compile(r'resource\s+"([a-zA-Z0-9_]+)"')


def run_security_check_eval():
    from src.llm_checks.security_check import check_module_security

    golden_path = REPO_ROOT / "eval" / "golden_sets" / "security_check_golden.csv"
    modules_dir = REPO_ROOT / "data" / "sample-repos" / "infra-modules" / "modules"

    rows_out = []
    with open(golden_path) as f:
        for row in csv.DictReader(f):
            module_name = row["module"]
            expected_flag = row["expected_flag"] == "true"
            resource_text = (modules_dir / module_name / "main.tf").read_text()

            try:
                findings = check_module_security(module_name, resource_text)
                actual_flag = len(findings) > 0
                # Capture WHAT it actually found, not just whether it
                # found something — a bare pass/fail tells you nothing
                # about why an over-flag or under-flag happened.
                actual_findings_text = " | ".join(
                    f"[{finding.severity}] {finding.issue}: {finding.reasoning}"
                    for finding in findings
                )
                error = ""
            except Exception as e:
                actual_flag = None
                actual_findings_text = ""
                error = str(e)

            passed = (actual_flag == expected_flag) if actual_flag is not None else None
            rows_out.append({
                "module": module_name,
                "expected_flag": expected_flag,
                "actual_flag": actual_flag,
                "pass": passed,
                "actual_findings": actual_findings_text,
                "expected_reason": row["reason"],
                "error": error,
            })

    _write_report("security_check", rows_out)


def _load_module_for_duplicate_check(name: str):
    """
    NOTE: this repo's sample modules have no README.md (unlike the
    module-wise project this was adapted from), so there's no real
    prose "description" to feed the check. Using raw main.tf content
    as a stand-in — this is a known simplification, not the intended
    real input shape. If duplicate_check results look unreliable,
    revisit this before assuming the check/prompt itself is wrong.
    """
    modules_dir = REPO_ROOT / "data" / "sample-repos" / "infra-modules" / "modules"
    text = (modules_dir / name / "main.tf").read_text()
    resource_types = RESOURCE_TYPE_RE.findall(text)
    return text, resource_types


def run_duplicate_check_eval():
    from src.llm_checks.duplicate_check import check_duplicate_capability

    golden_path = REPO_ROOT / "eval" / "golden_sets" / "duplicate_check_golden.csv"
    rows_out = []
    with open(golden_path) as f:
        for row in csv.DictReader(f):
            module_a, module_b = row["module_a"], row["module_b"]
            expected_similar = row["expected_similar"] == "true"

            try:
                desc_a, resources_a = _load_module_for_duplicate_check(module_a)
                desc_b, resources_b = _load_module_for_duplicate_check(module_b)
                finding = check_duplicate_capability(
                    module_a, module_b, desc_a, desc_b, resources_a, resources_b,
                )
                actual_similar = finding.similar
                actual_reasoning = f"[{finding.confidence}] {finding.reasoning}"
                error = ""
            except Exception as e:
                actual_similar = None
                actual_reasoning = ""
                error = str(e)

            passed = (actual_similar == expected_similar) if actual_similar is not None else None
            rows_out.append({
                "module_a": module_a,
                "module_b": module_b,
                "expected_similar": expected_similar,
                "actual_similar": actual_similar,
                "pass": passed,
                "actual_reasoning": actual_reasoning,
                "expected_reason": row["reason"],
                "error": error,
            })

    _write_report("duplicate_check", rows_out)


def _write_report(name: str, rows: list[dict]):
    out_dir = REPO_ROOT / "eval" / "results"
    out_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{name}_{timestamp}.csv"

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    passed = sum(1 for r in rows if r.get("pass") is True)
    failed = sum(1 for r in rows if r.get("pass") is False)
    unknown = sum(1 for r in rows if r.get("pass") is None)

    print(f"\n{name} eval results -> {out_path}")
    print(f"  passed:  {passed}")
    print(f"  failed:  {failed}")
    print(f"  unknown: {unknown} (error during check execution — see 'error' column)")
    if failed:
        print("\n  FAILED ROWS (read these by hand before trusting this check):")
        for r in rows:
            if r.get("pass") is False:
                print(f"    - {r}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target in ("security_check", "all"):
        run_security_check_eval()
    if target in ("duplicate_check", "all"):
        run_duplicate_check_eval()