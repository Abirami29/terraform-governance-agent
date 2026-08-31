"""
scripts/run_audit.py — runs the full orchestrator graph, pauses at
the human_review interrupt, asks YOU for a real approve/reject via
the terminal, then resumes and shows whether the report actually got
written.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph.types import Command
from src.orchestrator.graph import build_graph

graph = build_graph()
config = {"configurable": {"thread_id": "manual-run-1"}}

initial_state = {
    "repos_dir": "data/sample-repos",
    "version_drift": {},
    "unused_modules": [],
    "module_results": {},
    "duplicate_findings": [],
    "errors": [],
    "report_text": "",
    "human_decision": "",
    "report_written_to": "",
}

result = graph.invoke(initial_state, config=config)

# When interrupt() fires, LangGraph returns a state dict containing
# an "__interrupt__" key instead of running past that node — this is
# how we detect we're paused rather than finished.
if "__interrupt__" in result:
    interrupt_payload = result["__interrupt__"][0].value
    print(interrupt_payload["report"])
    print()
    decision = input(f"{interrupt_payload['instructions']} > ").strip().lower()

    final_result = graph.invoke(Command(resume=decision), config=config)

    print("\n--- AFTER RESUME ---")
    print(f"decision recorded: {final_result.get('human_decision')}")
    print(f"report written to: {final_result.get('report_written_to') or '(not written — rejected)'}")
else:
    print("No interrupt fired — check human_review node is wired correctly.")
    print(result)