"""
ITERATION 3 — human-in-the-loop mechanics.

These are arguably the most important tests in the whole repo: the
entire pitch of this project is "nothing gets written without human
approval." If this specific behavior is wrong, the project's central
claim is wrong, no matter how good the checks are. Test it directly
and explicitly rather than assuming the framework (LangGraph
interrupt/checkpointer) just handles it correctly by default.

NOTE: these are written against a minimal fake graph node so they can
run without a real LangGraph + LLM setup. Once src/orchestrator/graph.py
is implemented, port the same assertions to run against the real
compiled graph — the behavior being tested doesn't change, only what
you're calling.
"""
from pathlib import Path


class FakeReviewNode:
    """
    Minimal stand-in for the human_review interrupt node's write
    behavior, isolated from LangGraph so this test doesn't need a
    live checkpointer/LLM to prove the core contract: reject must
    never write, approve must always write.
    """
    def __init__(self, target_file: Path):
        self.target_file = target_file
        self.original_content = target_file.read_text() if target_file.exists() else None

    def apply(self, decision: str, new_content: str):
        if decision == "approve":
            self.target_file.write_text(new_content)
        elif decision == "reject":
            pass  # explicitly a no-op — this line is the test's whole point
        else:
            raise ValueError(f"unknown decision: {decision}")


def test_reject_leaves_file_completely_unchanged(tmp_path):
    """
    WHAT: create a file, run the review node with decision="reject"
    and a proposed new_content, then check the file on disk.
    WHY IT MATTERS: this is the single most important test in the
    project. If reject silently writes anyway, the entire "human
    approves before anything happens" claim in the framework doc is
    false, and nobody would find out until it actually overwrote
    something in a real run.
    PASS: file content on disk is byte-for-byte identical to before
    the review node ran.
    FAIL: if the content changed at all, decision handling has a bug
    — check for an inverted if/else or a write call outside the
    approve branch.
    """
    target = tmp_path / "README.md"
    target.write_text("original content\n")

    node = FakeReviewNode(target)
    node.apply(decision="reject", new_content="LLM-drafted replacement\n")

    assert target.read_text() == "original content\n"


def test_approve_actually_writes_the_new_content(tmp_path):
    """
    WHAT: same setup as above, but decision="approve".
    WHY IT MATTERS: positive-case counterpart — confirms approve
    isn't ALSO a silent no-op (a bug that would look safe but would
    mean the "apply on approval" half of the feature doesn't work at
    all).
    PASS: file content matches the proposed new_content exactly.
    FAIL: check the approve branch is actually calling write_text,
    and that new_content is being passed through unmodified.
    """
    target = tmp_path / "README.md"
    target.write_text("original content\n")

    node = FakeReviewNode(target)
    node.apply(decision="approve", new_content="LLM-drafted replacement\n")

    assert target.read_text() == "LLM-drafted replacement\n"


def test_unknown_decision_raises_rather_than_defaulting_to_write():
    """
    WHAT: pass a decision string that isn't "approve" or "reject"
    (e.g. a typo, or a future "retry"/"escalate" value from the
    6-way HITL taxonomy that isn't wired into this node yet).
    WHY IT MATTERS: the unsafe default here would be to fall through
    to a write on anything that isn't literally "reject" — that's a
    fail-open design and it's the wrong direction for a tool whose
    whole point is a safety gate. Fail-closed (raise, don't write) is
    the correct default until a decision type is explicitly handled.
    PASS: ValueError is raised, and (implicitly, since the code never
    reaches a write call) nothing is written to disk.
    FAIL: if this doesn't raise, some code path defaults to treating
    unrecognized input as approval — audit the review node's
    decision-handling for a bare `else: write(...)`.
    """
    import pytest
    node = FakeReviewNode(Path("/tmp/nonexistent-for-this-test.md"))
    with pytest.raises(ValueError):
        node.apply(decision="retry", new_content="whatever")
