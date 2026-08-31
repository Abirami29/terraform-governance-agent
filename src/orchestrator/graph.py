"""
First version of the audit orchestrator. Deliberately SEQUENTIAL, not
parallel fan-out — that's a real simplification, noted so it isn't
mistaken for the final design. No human-in-the-loop yet: this only
proves the graph runs end-to-end and produces one merged report.
Interrupt/approval gets added on top of this once this part is
verified working for real.

Each node wraps its own risky calls in try/except internally, rather
than letting exceptions propagate — LangGraph does not automatically
catch node exceptions and continue; an uncaught exception here would
crash the whole graph invocation, which would violate this project's
own fault-tolerance policy (see tests/test_fault_injection.py, which
tests this same pattern in isolation).
"""
from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

from src.deterministic.graph_queries import find_version_drift, find_unused_modules
from src.deterministic.terraform_validate import validate_module, TerraformNotInstalled
from src.deterministic.tflint_check import run_tflint, TflintNotInstalled
from src.deterministic.deletion_protection_check import check_deletion_protection
from src.llm_checks.security_check import check_module_security
from src.llm_checks.duplicate_check import check_duplicate_capability
from src.diffing.git_diff_scope import changed_tf_files


class AuditState(TypedDict):
    repos_dir: str
    version_drift: dict
    unused_modules: list
    module_results: dict
    duplicate_findings: list
    errors: list
    report_text: str
    human_decision: str
    report_written_to: str


def _module_dirs(repos_dir: str) -> list[Path]:
    modules_root = Path(repos_dir) / "infra-modules" / "modules"
    return sorted(p for p in modules_root.iterdir() if p.is_dir())


def structural_audit(state: AuditState) -> dict:
    """Deterministic, whole-repo-set checks — version drift, orphans."""
    repos_dir = Path(state["repos_dir"])
    errors = list(state.get("errors", []))
    try:
        drift = find_version_drift(repos_dir)
        drift_serializable = {k: [r.version for r in v] for k, v in drift.items()}
    except Exception as e:
        drift_serializable = {}
        errors.append(f"structural_audit (version_drift): {e}")

    try:
        unused = find_unused_modules(repos_dir)
    except Exception as e:
        unused = []
        errors.append(f"structural_audit (unused_modules): {e}")

    return {"version_drift": drift_serializable, "unused_modules": unused, "errors": errors}



def module_audit(state: AuditState) -> dict:
    """
    Per-module deterministic + LLM checks — SCOPED to changed
    modules only via git diff, not every module every run.
    """
    results = {}
    errors = list(state.get("errors", []))
    repos_dir = Path(state["repos_dir"])

    changed_files = changed_tf_files(repos_dir / "infra-modules")
    changed_module_dirs = sorted({f.parent for f in changed_files})

    if not changed_module_dirs:
        changed_module_dirs = _module_dirs(state["repos_dir"])

    for module_dir in changed_module_dirs:
        name = module_dir.name
        module_result = {}

        try:
            v = validate_module(module_dir)
            module_result["validate"] = {"valid": v.valid, "error": v.error_message}
        except TerraformNotInstalled as e:
            module_result["validate"] = {"skipped": True, "reason": str(e)}
            errors.append(f"{name} validate: {e}")
        except Exception as e:
            module_result["validate"] = {"skipped": True, "reason": str(e)}
            errors.append(f"{name} validate: {e}")

        try:
            lint = run_tflint(module_dir)
            module_result["tflint"] = {
                "clean": lint.clean,
                "issues": [f"[{i.rule}] {i.message}" for i in lint.issues],
            }
        except TflintNotInstalled as e:
            module_result["tflint"] = {"skipped": True, "reason": str(e)}
            errors.append(f"{name} tflint: {e}")
        except Exception as e:
            module_result["tflint"] = {"skipped": True, "reason": str(e)}
            errors.append(f"{name} tflint: {e}")

        try:
            resource_text = (module_dir / "main.tf").read_text()
        except Exception as e:
            errors.append(f"{name} read main.tf: {e}")
            results[name] = module_result
            continue

        try:
            dp_issues = check_deletion_protection(name, resource_text)
            module_result["deletion_protection"] = [i.issue for i in dp_issues]
        except Exception as e:
            module_result["deletion_protection"] = {"skipped": True, "reason": str(e)}
            errors.append(f"{name} deletion_protection: {e}")

        try:
            sec_findings = check_module_security(name, resource_text)
            module_result["security"] = [
                f"[{f.severity}] {f.issue}: {f.reasoning}" for f in sec_findings
            ]
        except Exception as e:
            module_result["security"] = {"skipped": True, "reason": str(e)}
            errors.append(f"{name} security_check: {e}")

        results[name] = module_result

    return {"module_results": results, "errors": errors}


# NOTE: hardcoded to the one known planted pair for this first
# version — checking all C(n,2) module pairs is a real scope
# decision (cost scales quadratically with module count) that should
# be made deliberately, not silently added here.
KNOWN_DUPLICATE_CANDIDATE_PAIRS = [("s3-bucket-standard", "s3-bucket-legacy")]


def duplicate_audit(state: AuditState) -> dict:
    import re
    resource_type_re = re.compile(r'resource\s+"([a-zA-Z0-9_]+)"')
    modules_root = Path(state["repos_dir"]) / "infra-modules" / "modules"

    findings = []
    errors = list(state.get("errors", []))

    for module_a, module_b in KNOWN_DUPLICATE_CANDIDATE_PAIRS:
        try:
            text_a = (modules_root / module_a / "main.tf").read_text()
            text_b = (modules_root / module_b / "main.tf").read_text()
            result = check_duplicate_capability(
                module_a, module_b, text_a, text_b,
                resource_type_re.findall(text_a), resource_type_re.findall(text_b),
            )
            findings.append(
                f"{module_a} <-> {module_b}: similar={result.similar} "
                f"[{result.confidence}] {result.reasoning}"
            )
        except Exception as e:
            errors.append(f"duplicate_audit ({module_a}, {module_b}): {e}")

    return {"duplicate_findings": findings, "errors": errors}

def merge_report(state: AuditState) -> dict:
    """
    Builds one human-readable report string from everything the
    fan-out nodes produced. This is what the human actually reads at
    the interrupt point — not the raw state dict.
    """
    lines = ["=== TERRAFORM GOVERNANCE AUDIT REPORT ===", ""]

    lines.append("VERSION DRIFT:")
    lines.append(str(state.get("version_drift", {})) or "  none")
    lines.append("")

    lines.append("UNUSED MODULES:")
    lines.append(str(state.get("unused_modules", [])) or "  none")
    lines.append("")

    lines.append("PER-MODULE FINDINGS:")
    for name, r in state.get("module_results", {}).items():
        lines.append(f"  --- {name} ---")
        for key, val in r.items():
            lines.append(f"    {key}: {val}")
    lines.append("")

    lines.append("DUPLICATE FINDINGS:")
    for f in state.get("duplicate_findings", []):
        lines.append(f"  {f}")
    lines.append("")

    if state.get("errors"):
        lines.append("ERRORS / SKIPPED:")
        for e in state["errors"]:
            lines.append(f"  - {e}")

    return {"report_text": "\n".join(lines)}


def human_review(state: AuditState) -> dict:
    """
    Pauses graph execution and hands the report to a human. Execution
    resumes when the graph is invoked again with a Command(resume=...)
    against the same thread — interrupt() returns whatever value was
    passed to that resume call.

    NOTE: this is the first real test of interrupt()/checkpointer
    mechanics in this project — everything before this was tested
    against a fake stand-in node (see tests/test_hitl_interrupt.py).
    If this behaves unexpectedly on first run, that's expected — read
    the actual error/traceback rather than assuming the design is
    wrong.
    """
    decision = interrupt({
        "report": state["report_text"],
        "instructions": "Reply with 'approve' or 'reject'.",
    })
    return {"human_decision": decision}


def apply_decision(state: AuditState) -> dict:
    """
    The actual safety gate: reject must be a complete no-op, approve
    must actually write. Same contract already proven in isolation by
    tests/test_hitl_interrupt.py — this is that same contract, for
    real, inside the real graph for the first time.
    """
    if state.get("human_decision") == "approve":
        out_path = Path("eval/results") / "latest_audit_report.txt"
        out_path.parent.mkdir(exist_ok=True)
        out_path.write_text(state["report_text"])
        return {"report_written_to": str(out_path)}
    return {"report_written_to": ""}

def build_graph():
    graph = StateGraph(AuditState)
    graph.add_node("structural_audit", structural_audit)
    graph.add_node("module_audit", module_audit)
    graph.add_node("duplicate_audit", duplicate_audit)
    graph.add_node("merge_report", merge_report)
    graph.add_node("human_review", human_review)
    graph.add_node("apply_decision", apply_decision)

    graph.add_edge(START, "structural_audit")
    graph.add_edge("structural_audit", "module_audit")
    graph.add_edge("module_audit", "duplicate_audit")
    graph.add_edge("duplicate_audit", "merge_report")
    graph.add_edge("merge_report", "human_review")
    graph.add_edge("human_review", "apply_decision")
    graph.add_edge("apply_decision", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)