# Next Iteration — Planned Work

This tracks scoped-out work, deliberately deferred to keep the current
submission honest about what's built vs. planned. Everything below was
discussed and estimated during the initial build session; estimates
reflect that session's actual pace (LLM-facing work consistently took
~2x the paper estimate once real testing started), not optimistic
best-case numbers.

## 1. Doc-drift check + `draft_doc_update`

One of the three original framing questions for this project
(alongside deterministic Cypher and drift determinism) — the only one
of the three not yet built.

**Build:**
- Adapt `check_structural_drift` / `check_narrative_alignment` from
  the `module-wise` project's `enrichment.py` into this repo's style
  (LLM extracts a claim from a comment → deterministic code checks it
  against parsed `.tf` facts, same hybrid pattern already documented
  in this project's design notes)
- New `draft_doc_update` LLM node — drafts corrected doc text for
  modules flagged with drift
- Extend `merge_report` / `human_review` to surface doc diffs
  alongside audit findings, gated by the same approve/reject/edit
  flow already proven working end-to-end

**Testing — do not skip, based on this session's experience:**
- Needs its own golden set: planted stale-comment cases (module where
  a comment claims something false about the actual config) +
  negative cases (comments that are accurate)
- Run 3x for consistency before trusting any single pass/fail, same
  discipline used for `security_check` and `duplicate_check` — every
  LLM-facing check this session needed at least one real prompt fix
  after the first "looks fine" pass turned out to be wrong or flaky

**Estimate:** 2–3 hours realistic (not the ~1 hour it looks like on paper)

## 2. Provider upgrade feature (on-demand trigger)

The most genuinely "agentic" piece — responds to an ad hoc human
directive ("upgrade the aws provider to 5.x") rather than running a
fixed checklist, using the multi-repo blast-radius data already built.

**Build:**
- Add `required_providers` version constraints to sample module data
  (currently absent — needs to be added before this can work at all)
- New deterministic blast-radius-for-provider query (which
  repos/modules reference a given provider, at what version)
- `draft_diff` — templated version-constraint bump across affected
  files, surfaced with any known-breaking-change notes
- Git branch + commit on approval — **a new kind of write action**,
  untested so far (everything proven this session was a single-file
  write, not a git operation) — reuses the existing `human_review`
  interrupt/approve/reject gate, doesn't need a new HITL mechanism

**Estimate:** 2.5–3.5 hours realistic

## 3. Stretch — AWS-backed live demo

- Real `terraform plan` (and possibly `apply`) against an actual AWS
  account, for genuine resource-level destroy/replace detection —
  currently the audit only reasons at the module-reference level via
  the graph, not actual resource-level plan output
- Use a cheap, disposable resource type for any live demo (S3 bucket
  or a small EC2 instance), torn down immediately after
- Credentials via a `.gitignore`'d `terraform.tfvars`, never
  committed; document clearly that this isn't reusable by anyone
  without their own AWS account

## 4. Stretch — deterministic security scanner layer

- Add `checkov` and/or `tfsec` alongside the existing `tflint` +
  `tflint-ruleset-aws` layer
- Would likely absorb some of what `security_check`'s LLM currently
  catches (open security groups, missing encryption, missing
  public-access-block) into a faster, cheaper, non-flaky deterministic
  layer — consistent with this project's established principle:
  deterministic wherever the answer doesn't require judgment, LLM
  only for genuine ambiguity
- Would shrink `security_check`'s prompt scope further, likely
  improving its reliability on whatever judgment-only findings remain

## Current state, for context (as of this session)

Fully built and verified: all deterministic checks (version drift,
orphan modules, blast radius, `terraform validate`, `tflint` +
AWS deprecation plugin, deletion-protection), both LLM checks
(`security_check`, `duplicate_check` — verified 3x each, confirmed
free of test-data contamination after a real spoiler-comment bug was
found and fixed), the LangGraph orchestrator (fan-out, merge, fault
tolerance, diff-scoping — proven working against real git history
across genuinely separate sample repos), and the full HITL
interrupt/approve/reject/write cycle — proven end-to-end with real
human input, both branches (reject leaves disk untouched, approve
writes exactly what was shown at the review prompt) independently
verified on disk, not just from printed output.