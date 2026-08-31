# Terraform Governance Agent

An agent that audits a Terraform module ecosystem across multiple
repos, using deterministic checks where the answer is a fact and LLM
judgment only where the answer requires genuine reasoning — with a
human approval gate before anything gets written to disk.

## One-liner

This agent helps a platform engineer audit their shared Terraform
module ecosystem across 4 repos, replacing manual grep-and-tribal-
knowledge checks. It runs drift, orphan-module, deletion-protection,
security, and duplication checks on its own using deterministic graph
queries plus LLM analysis, hands off to a human before any file is
written, and I'll know it works when a platform engineer gets a
trustworthy cross-repo audit report in one run instead of manually
checking each repo by hand.

## What's actually built (verified, not just claimed)

**Deterministic checks — no LLM, no ambiguity:**
- Version drift across repos (`src/deterministic/graph_queries.py`)
- Orphaned modules with zero consumers (same file)
- Blast-radius lookup (which repos consume a given module)
- Syntax/validity via `terraform validate` (`terraform_validate.py`)
- Deprecated arguments/instance types via `tflint` + the
  `tflint-ruleset-aws` plugin (`tflint_check.py`)
- Missing deletion protection (`deletion_protection_check.py`) —
  moved here from an LLM prompt after 3 consecutive eval runs showed
  the LLM didn't reliably catch it; a fixed presence/value check
  belongs in the deterministic layer, not the LLM layer

**LLM-judgment checks — only where genuine reasoning is needed:**
- `security_check` — context-dependent security risk (open network
  access, missing encryption, missing public-access blocking)
- `duplicate_check` — whether two modules serve a substantially
  similar purpose

Both were verified against a human-labeled golden dataset
(`eval/golden_sets/`), run 3x each for consistency before being
trusted — one real reliability problem was found and fixed this way
(see "What went wrong" below), and one real bug was found where
LLM-facing sample data accidentally contained comments describing the
expected test answer, contaminating the results; that was found,
fixed, and every check re-verified clean afterward.

**Orchestrator (`src/orchestrator/graph.py`):** a LangGraph state
graph that fans out to all the above, merges results into one report,
and — critically — pauses at a real `interrupt()` for human approval
before anything is written. Both branches are independently verified
on disk, not just from printed output: **reject** leaves the
filesystem completely untouched; **approve** writes exactly what was
shown at the review prompt, no silent changes in between.

**Diff-scoping:** only changed `.tf` files get re-checked, not the
whole repo every run — proven working against real git history
across genuinely separate sample repos (`infra-modules`,
`service-webshop`, `service-billing`, `service-analytics` are each
their own git repo, matching the real multi-repo shape this project
represents).

## What's deliberately NOT built yet

See `NEXT_ITERATION.md` for the full list and honest time estimates:
doc-drift check + `draft_doc_update`, the on-demand provider-upgrade
feature, an AWS-account-backed live demo, and a `checkov`/`tfsec`
deterministic security layer.

## What went wrong, and what that shows

Two real problems were found and fixed during development, not
smoothed over:

1. **A deletion-protection finding (`skip_final_snapshot=true`) was
   asked of the LLM `security_check` and failed 3 consecutive
   golden-set runs (0/3).** Rather than keep tuning the prompt, this
   was recognized as a fixed presence/value check that belongs in the
   deterministic layer — moved there, and it's been 100% reliable
   since, at zero LLM cost.
2. **Sample `.tf` files originally contained explanatory comments
   describing what each planted test case was for** (e.g. "this
   should be flagged as a duplicate"). The LLM was reading those
   comments as part of the resource text and echoing them back as
   findings — contaminating every golden-set result up to that point.
   Found via manual inspection of a real orchestrator run, fixed by
   moving all test-case documentation into `NOTES.md` (never read by
   any check), and every check re-verified 3x clean afterward.

Both are documented here deliberately — the point of eval-driven
development is catching exactly this kind of thing before it ships,
not pretending every run passed on the first try.

## Running it

```bash
pip install -r requirements.txt
pytest tests/ -v                          # deterministic + plumbing tests
python eval/run_eval.py security_check    # LLM judgment eval
python eval/run_eval.py duplicate_check
python scripts/run_audit.py               # full orchestrator, real HITL prompt
```

See `.env.example` for required environment variables (Nebius API
credentials).

## Directory structure

```
src/
  deterministic/     — graph queries, terraform validate, tflint, deletion-protection
  diffing/           — git diff scoping
  llm_checks/        — security_check, duplicate_check
  llm/               — Nebius client wrapper
  orchestrator/      — LangGraph graph: fan-out, merge, HITL interrupt
eval/
  golden_sets/       — human-labeled expected output per LLM check
  run_eval.py        — runs a check against its golden set, writes a report
data/sample-repos/   — 4 independent git repos with deliberately planted
                        issues (see NOTES.md inside for what's planted where)
tests/               — pytest suite, one docstring per test explaining
                        what/why/pass/fail
NEXT_ITERATION.md    — deferred work, with honest time estimates
```