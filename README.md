# Terraform Governance Agent — Test Suite

This repo's tests are split into two categories on purpose, because
they answer two different questions.

## The two kinds of "test" in this repo

**1. `tests/` — pytest, plain pass/fail, run on every change.**
These cover everything deterministic: graph queries, `terraform
validate`, diff scoping, and the *mechanics* of the human-approval
gate and the fault-tolerance policy. There's no ambiguity in a
correct answer here — a module either has zero consumers or it
doesn't. If one of these fails, the code is wrong; fix the code, not
the test.

**2. `eval/run_eval.py` — not pytest, run manually, produces a report.**
This covers the two LLM-judgment checks (`security_check`,
`duplicate_check`). These don't have a single unambiguous right
answer the way a graph query does — they're judgment calls, so they
get evaluated against a human-labeled golden dataset
(`eval/golden_sets/*.csv`) and the output is a **CSV report you read
by hand**, not a boolean. This follows the eval-driven development
process: golden dataset → run → distill to pass/fail per row → read
every failure and write down why → only then consider an LLM-judge
layer if you want to scale past manual reading.

Do not try to make the LLM-judgment checks pass a pytest assert
directly against "the LLM said the right thing" — that's exactly the
kind of test that gives false confidence, because a single run of a
non-deterministic model proves nothing about the next run.

## Running the deterministic suite

```bash
pip install -r requirements.txt
pytest tests/ -v
```

Some tests are skipped automatically if a tool isn't installed
(`terraform validate` tests skip if the `terraform` CLI isn't on
PATH — check the skip count in the summary, don't assume "0 failed"
means everything ran).

## Running the eval report

Wire a real LLM client into `src/llm_checks/security_check.py`'s
`_call_llm()` first — it raises `NotImplementedError` by default so
nothing accidentally makes a network call during normal `pytest`
runs.

```bash
python eval/run_eval.py security_check
python eval/run_eval.py duplicate_check
```

Output lands in `eval/results/<check>_<timestamp>.csv`. Read the
failed rows. If a row fails and the LLM's stated reasoning actually
looks right to you on inspection, the golden-set label might be
wrong, not the check — golden sets are living documents, update them
when you're confident the original label was the mistake.

## What's planted in the sample data (`data/sample-repos/`)

This mirrors the "bake in intentional inconsistencies" pattern —
every check has at least one known positive case and one known
negative case in the data, not just positive cases, so tests catch
over-flagging as well as under-flagging.

| Planted issue | Where | Which check catches it |
|---|---|---|
| Orphan module (0 consumers) | `sqs-queue` | `find_unused_modules` |
| Version drift (v1.0.0 vs v1.2.0) | `rds-postgres` | `find_version_drift` |
| Open security group (0.0.0.0/0 on :22) | `security-group-web` | `security_check` (LLM) + should also be caught by `tflint`/`checkov` (deterministic, not yet wired) |
| Duplicate-purpose modules | `s3-bucket-standard` / `s3-bucket-legacy` | `duplicate_check` (LLM) |
| Stale doc comment (claims encryption disabled, resource has it enabled) | `rds-postgres` README/comment | doc-drift check (not yet implemented in this scaffold) |
| Clean/negative case | `vpc-base` | used as the "don't over-flag this" case across multiple checks |

If you add a new planted issue, add it to this table — it's the
single source of truth for "what should this audit actually catch,"
which doubles as documentation for your project write-up's "how do I
know it works" section.

## Directory structure

```
src/
  deterministic/     — graph queries, no LLM, no ambiguity
  diffing/           — git diff scoping (only re-check what changed)
  llm_checks/        — security_check, duplicate_check (LLM judgment)
  orchestrator/       — LangGraph wiring (not yet implemented in this scaffold)
eval/
  golden_sets/       — human-labeled expected output per LLM check
  run_eval.py        — runs a check against its golden set, writes a report
  results/           — timestamped CSV reports land here (gitignored)
tests/
  test_deterministic_graph_queries.py  — Iteration 1
  test_terraform_validate.py           — Iteration 1
  test_git_diff_scoping.py             — Iteration 1
  test_llm_checks_eval.py              — Iteration 2 (plumbing, not judgment quality)
  test_hitl_interrupt.py               — Iteration 3 (the core safety claim)
  test_fault_injection.py              — Iteration 3 (failure-handling policy)
```
