# Tech Lead State Protocol 1.0

This document defines the portable, provider-neutral `.techlead/` state
contract. Codex and Claude Code adapters may invoke roles differently, but they
must read and produce state with these semantics.

## Encoding

Every protocol record is UTF-8 Markdown with YAML frontmatter. Protocol 1.0
intentionally accepts a deterministic YAML subset so the distributed validator
does not need a package manager:

- top-level `key: value` pairs;
- strings, integers, booleans, and `null`;
- JSON-style inline arrays and objects (JSON is valid YAML);
- block arrays whose items are scalars; and
- full-line comments beginning with `#`.

Nested block maps, anchors, tags, and implicit dates are not part of protocol
1.0. Use inline JSON for structured values, such as acceptance criteria.

Every record includes `protocol_version: "1.0"` and a `kind`. Schemas live in
[`../schemas`](../schemas). Markdown bodies carry explanations and rationale;
frontmatter carries identity, lifecycle, references, and provenance that can be
checked mechanically.

## Project layout

```text
.techlead/
├── CHARTER.md
├── OVERVIEW.md
├── FRONTIER.md
├── RISKS.md
├── DECISIONS.md
└── work-items/<WI-id>/
    ├── WORK.md
    ├── revisions/<revision>.md
    ├── attempts/<attempt-id>.md
    ├── verifications/<verification-id>.md
    ├── resolutions/<revision>.md
    ├── evidence/
    └── INVALIDATION.md
```

`WORK.md` is the only mutable canonical record for a graph node. Files under
`revisions/`, `attempts/`, `verifications/`, and `resolutions/` become immutable
once referenced by a later record. `INVALIDATION.md` is historical and does not
rewrite earlier evidence.

## IDs and references

IDs are stable, opaque, and globally unique within a project:

| Entity | Pattern |
| --- | --- |
| Work item | `WI-001` |
| Assignment contract | `AC-001` |
| Attempt/result | `ATT-001` |
| Verification/evidence | `EV-001` |
| Resolution | `RES-001` |
| Invalidation | `INV-001` |
| Risk | `RISK-001` |
| Decision | `DEC-001` |

Work-item resolution references use `<work-item>@<revision>`, for example
`WI-001@r1`. File references are repository-relative POSIX paths and must not
escape the repository.

## Project records

- `CHARTER.md` (`project_charter`) contains human-authoritative intent.
- `OVERVIEW.md` (`project_overview`) indexes `current_resolutions`, every
  `historical_resolution`, and `current_facts`. Each fact contains its claim and
  one or more supporting resolution references. Current entries must resolve
  and must not point to an invalidated or suspended node revision.
- `FRONTIER.md` (`project_frontier`) lists the unresolved graph projection in
  `work_items`.
- `RISKS.md` (`risk_register`) stores structured `risks` with status, owner,
  affected and mitigation items, evidence, and residual uncertainty; each ID
  has a matching `## RISK-nnn` body heading.
- `DECISIONS.md` (`decision_register`) stores structured `decisions` with
  governing status, resolution provenance, and supersession links; each ID has
  a matching `## DEC-nnn` heading.

## Work graph

`WORK.md` records decomposition (`parents`/`children`), scheduling
(`dependencies`/`dependents`), symmetric related context (`related`),
replacement (`replaces`/`replaced_by`), and revision-transition ownership
(`revision_transitions`). Every relationship has a mechanically checked
backlink.

The allowed states are:

`DRAFT`, `READY`, `DECOMPOSED`, `IN_PROGRESS`, `BLOCKED`, `SUBMITTED`,
`VERIFYING`, `NEEDS_CHANGES`, `PENDING_HUMAN`, `PENDING_PLAN_REVIEW`,
`REVISING`, `RESOLVED`, `REPLACED`, and `INVALIDATED`.

Additional invariants include:

- a `READY` item has only `RESOLVED` dependencies;
- a `DECOMPOSED` item has at least one child;
- an active assignment points to a contract for its active revision;
- a `RESOLVED` item has a resolution for its active revision;
- an `INVALIDATED` item has `INVALIDATION.md`;
- a `REVISING` item names at least one transition item; and
- a transition item sets both `target_node` and `from_revision`, while its
  target lists it in `revision_transitions`.

## Assignment contracts and role results

An `assignment_contract` binds one worker session to one work-item revision.
Its `criteria` array contains objects with a criterion `id` and one or more
required methods from `worker_attested`, `deterministic`, `independent_review`,
or `human_signoff`. Criterion prose belongs in the Markdown body under the same
ID.

A `worker_result` reports one bounded execution attempt. It records its contract,
outcome, changed artifacts, evidence references, Git revisions, and any affected
work items. `PENDING_PLAN_REVIEW` is a result, not permission for the worker to
edit the graph.

A `plan_review_result` is the sub-tech-lead's impact-aware proposal. It records
the divergence source, affected nodes, proposed graph changes, and evidence.
Only the global tech lead applies the proposal.

A `verification` evaluates named criteria with exactly one method and an
outcome of `PASS`, `FAIL`, or `INCONCLUSIVE`. A `resolution` may be created only
when its referenced passing verifications cover every method required by every
criterion. The validator checks this coverage; the global tech lead still owns
the semantic judgment that the evidence is meaningful.

The global tech lead's result is the coordinated state transition itself:
updated canonical records plus any new immutable records. It does not rely on a
separate transcript or hidden provider state.

## Revisions, pivots, and invalidation

A pivoted primary node enters `REVISING` and lists a normal transition work item.
The transition sets `target_node` and `from_revision`. A later resolution of the
transition may publish the target's next revision after affected nodes and
artifacts are reconciled.

An invalidated descendant or consumer enters `INVALIDATED`; its
`INVALIDATION.md` records the revision that lost authority, the governing
transition item, affected facts and artifacts, and migration items. Historical
resolutions stay in the overview's historical index but leave its current
resolution set.

## Validation boundary

The validator checks syntax, schemas, ID uniqueness, paths, record placement,
graph links and backlinks, lifecycle preconditions, reference integrity,
frontier agreement, overview resolution indexes, and criterion coverage. It does
not decide whether a plan is wise, evidence is persuasive, a risk is severe, or
a human should approve a tradeoff.
