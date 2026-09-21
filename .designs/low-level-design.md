# Tech Lead Agent — Low-Level Design

> **Status:** Implementation in progress
> **Date:** 21 September 2026
> **Depends on:** [High-Level Design](./high-level-design.md), [Vision](./vision.md)

This document translates the approved architecture and protocol decisions into
an implementation sequence, use-case acceptance matrix, and release gates. The
high-level design remains authoritative for product boundaries, record
semantics, and human-versus-tool authority.

## 1. Implementation plan

### 1.1 Migration shape

Before this migration, the repository implemented the superseded Protocol 1.0
orchestrator: a fourteen-state work graph, five project-level registries,
assignment and result record families, pivot reconciliation, and packaged
worker, verifier, and sub-tech-lead agents. Protocol 2.0 replaces that design
rather than extending it.

Retain and adapt:

- the dependency-free Markdown/frontmatter parser;
- the small JSON-schema evaluator;
- the self-contained plugin-copy and deterministic packaging pattern;
- the public `techlead-state` executable shape; and
- the principle that provider adapters conform to shared fixtures.

Replace or remove:

- all Protocol 1.0 schemas, graph lifecycle checks, root registries, and
  conformance scenarios;
- `CHARTER.md`, `OVERVIEW.md`, `FRONTIER.md`, `RISKS.md`, and `DECISIONS.md`
  templates;
- assignment, attempt, verification, resolution, invalidation, and pivot
  record types;
- the `lead-project`, `reconcile-pivot`, and standalone validation skills;
- worker, verifier, sub-tech-lead, and global-orchestrator role definitions;
  and
- every packaged agent or hook.

Add three provider-neutral behavior specifications under `core/behaviors/`:
`review-work`, `create-work-item`, and `work-log`. Provider packages translate
only their invocation and tool instructions; these shared behaviors and the
Protocol 2.0 fixtures remain authoritative.

### 1.2 Phase 1 — Protocol 2.0 records and fixtures

Rewrite `core/protocol/PROTOCOL.md` around the multi-project control root and
the four record envelopes fixed in the high-level design:

- `PROJECT.md`;
- `work-items/WI-NNN-description/WORK.md`;
- `work-items/.../revisions/rN-description.md`; and
- `sessions/SES-NNN-description.md`.

Add exact, closed schemas for those records plus `.techlead-project`. The
validator infers record type from location rather than a `kind` field, and reads
`protocol_version` only from `PROJECT.md`. Replace the existing fixtures with
small filesystem snapshots for initialization, single-parent decomposition,
revision sign-off, session continuity, leaf resolution, exception roll-up,
completion review, terminal resolution, and multi-project attachment.

Protocol 1.0 state is never reinterpreted silently. The first Protocol 2.0
release detects it and returns a diagnostic directing the human to initialize a
separate Protocol 2.0 project. A later explicit migration command may import
Protocol 1.0 into a new directory, but it must stop for human decisions wherever
multi-parent, dependency, pivot, or invalidation semantics cannot be mapped to
the new tree.

### 1.3 Phase 2 — Resolution, attachment, and local discovery

Extend `techlead-state` with a provider-neutral resolver. Given a project
directory or an attached implementation workspace, it resolves in this order:

1. a valid local `.techlead` symlink;
2. an explicitly supplied project UUID and per-user registry mapping; or
3. one unambiguous project binding from `.techlead-project`.

If several bindings are possible, it returns a structured ambiguity error for
the skill to present to the human. Every resolved mapping is verified against
the target `PROJECT.md` UUID.

Implement these helper operations:

- `init --control-dir --name --title --root --workspace-id` creates a new
  descriptive project directory, `PROJECT.md`, and `WI-001` in `in-design`;
- `attach --project --workspace` updates the portable locator, the per-user
  UUID registry, the project-local attachment mapping, the link farm, and the
  current worktree's ignored `.techlead` symlink;
- `resolve-project` emits the selected canonical root for provider skills; and
- `repair-attachment` restores stale mappings and symlinks without changing
  canonical work-item state.

These operations never require Git, stage files, create commits, create
worktrees, or overwrite an existing project directory. They reject tracked
local symlinks, mappings, and generated snapshots.

### 1.4 Phase 3 — Validation and transactional mutations

Rewrite the cross-record validator around the narrow mechanical boundary fixed
in [High-Level Design §10](./high-level-design.md#10-poc-implementation-decisions).
Its checks include:

- exact envelopes, filename patterns, and descriptive suffixes;
- project, workspace, work-item, session, and revision identity uniqueness;
- one declared root, one parent per non-root item, parent existence, and an
  acyclic tree;
- state, active-revision, review-flag, terminal-resolution, and revision-chain
  invariants;
- session-to-item and session-to-workspace membership;
- canonical Markdown link syntax, workspace membership, local targets, and
  heading anchors; and
- Git-index safety when the surrounding directory happens to use Git.

External-URL reachability remains part of the active review because it depends
on host network permissions. Semantic sufficiency, materiality, alternative
coverage, resolution, and parallel safety remain outside deterministic code.

All mutations go through a transaction layer. It acquires the project-local
writer lock, re-reads preconditions, stages candidate files under ignored local
state, validates the overlaid project, replaces each touched file safely, and
rolls back on failure. Read-only commands do not acquire the writer lock, but
they retry or refuse while a writer holds it so they never project a partial
multi-file update.

ID allocation occurs inside the lock. Work-item and revision numbers come from
durable directories. Session allocation scans live session filenames and
surviving `SES-NNN` provenance in work-item bodies before choosing the next
number, so deleting a closed live-session file does not create an ambiguous
reference.

Provide internal mutation operations for:

- creating a child;
- applying a completed review, including an optional new revision;
- recording child and ancestor verdict links;
- setting or clearing `review_required`;
- registering, pausing, moving, or closing a session; and
- applying an explicitly approved multi-child creation and parent revision as
  one transaction.

The helper accepts the semantic decision selected by Tech Lead and the human;
it never decides which transition is correct.

### 1.5 Phase 4 — Shared Tech Lead behavior

Implement `review-work` as a state-dispatched workflow:

1. Resolve the project and item.
2. Register or reuse a dedicated `techlead-review` session. Refuse to relabel a
   design, exploration, implementation, or verification session.
3. Load `WORK.md`, the active semantic revision, the named design or outcome,
   parent context, child verdicts, and only the additional linked context needed
   for the decision.
4. Validate every link in the bounded review scope. Broken required links block
   the transition.
5. For `in-design`, adversarially examine explicit and implicit assumptions,
   material credible alternatives, requirements, decomposition, start
   conditions, coordination, outputs, and resolution conditions.
6. For an `in-working` leaf, record the externally supplied outcome and judge
   whether it covers the signed resolution conditions without claiming
   independent implementation verification.
7. For an `in-working` parent under an early exception review, synthesize the
   available verdicts immediately even if siblings remain unresolved, but do
   not resolve the parent. For an ordinary completion review, wait for every
   current child and synthesize all their verdicts. Recommend reaffirmation, a
   changed revision, additional explicitly approved children, or return to
   `in-design`; recommend resolution only when every child is resolved.
8. Ask one material human decision at a time with a recommendation. The human
   decides materiality and invalidation.
9. Build the candidate `WORK.md`, revision, child, and ancestor updates and
   submit them to the transaction helper.

The implementation creates `r1` only for an initial signed baseline and `rN+1`
only when that baseline changes. Editorial rewrites, reaffirmation, and
resolution under an unchanged baseline retain the current revision.

Implement `create-work-item` as a thin judgment-bearing workflow that requires
one explicit parent, chooses the next `WI-NNN`, creates a descriptive directory,
links the relevant parent context and presumptions, and always initializes the
child as unsigned `in-design`. It rejects a resolved parent. The same operation
may be called from `review-work` only after explicit in-session human approval.

Implement `work-log` as a routed skill with these actions:

- `init`, `attach`, `register-session`, `pause-session`, `close-session`, and
  `validate` delegate to deterministic helper operations;
- `status` renders the current tree, review-due items, and live sessions from a
  deterministic projection; and
- `next` combines that projection with semantic start conditions and
  coordination context to return one or more `(action, work item)` pairs with
  explicit parallel-safety reasoning.

### 1.6 Phase 5 — Parent roll-up and terminal resolution

Applying a leaf review updates the leaf and walks its single-parent chain in the
same transaction. Each affected ancestor receives a concise linked verdict, not
a copy of the full child outcome. Tech Lead identifies which signed assumptions
are confirmed or challenged.

- An explicit material challenge sets `review_required: true` on each affected
  `in-working` ancestor immediately, even while siblings remain unresolved.
- Ordinary completion waits until every current child is `resolved`, then sets
  `review_required: true` on the immediate parent.
- A parent remains signed while review is pending. Only explicit `review-work`
  may reaffirm it, revise it, return it to `in-design`, or resolve it.
- Resolving a parent repeats roll-up toward its parent.
- A resolved item is terminal, has only resolved children, and cannot receive a
  new child. Later discoveries create linked new work under an unresolved
  ancestor or a new project when the old root is resolved.

### 1.7 Phase 6 — Claude Code vertical slice

Replace the current Claude skills with exactly:

- `/techlead:review-work`;
- `/techlead:create-work-item`; and
- `/techlead:work-log`.

Remove packaged agents, old roles, pivot behavior, and hook assumptions. Copy
the shared protocol, schemas, templates, helper, and conformance fixtures into
the plugin as today, then update packaging tests and marketplace descriptions.
Run the complete demonstration scenario in Claude Code before treating the
adapter as complete.

### 1.8 Phase 7 — Codex adapter and parity

Create the Codex plugin only after the Claude vertical slice passes the shared
fixtures. Package the same three capabilities as `$review-work`,
`$create-work-item`, and `$work-log`, with no additional namespace in normal
Codex invocation. Reuse the same helper and records; implement only Codex-native
skill metadata, session-ID discovery, installation layout, and permission
guidance.

Run identical scenario fixtures and compare canonical project state while
ignoring allowed provider-specific presentation and session metadata. A
provider adapter may not introduce a state, record type, or transition absent
from the shared protocol.

## 2. Use-case implementation and acceptance matrix

| Use case | Implementation path | Acceptance evidence |
| --- | --- | --- |
| Initialize one project under a multi-project control root | `$work-log init` creates a collision-safe descriptive directory, UUID, `PROJECT.md`, root `WI-001`, locator binding, registry entry, and local symlink. | Two projects coexist under one control root; neither requires Git; an existing target is never overwritten. |
| Attach multiple repositories, clones, and worktrees | Resolver, `.techlead-project`, per-user UUID registry, per-project local mappings, and per-worktree `.techlead` selection cooperate. | One project spans several workspace IDs; one workspace binds several projects; two worktrees select different projects. |
| Create a child from a parent | `$create-work-item` allocates an ID under lock, creates `WI-NNN-description/WORK.md`, sets the single parent, and inserts narrow inherited-context links. | Child is always `in-design`; resolved parents and missing or ambiguous parents are rejected. |
| Bar-raise an initial design or task | `$review-work` registers a review session, validates links, grills assumptions and alternatives, checks decomposition and outputs, and applies sign-off. | Pass creates descriptive `r1` and moves to `in-working`; incomplete review leaves open findings and `in-design`. |
| Distinguish editorial changes from a material revision | Tech Lead compares current meaning with the active semantic baseline and asks the human when materiality is uncertain. | Editorial rewrite keeps `active_revision`; an accepted baseline change creates the next descriptive revision. No commit or content hash is required. |
| Resume and track external work | `$work-log register-session` combines attachment and session registration; pause, move, and close update one `SES-NNN` record and local worktree mapping. | Provider ID remains resumable; one session may link several items; role switching is rejected; optional branch/revision may be absent. |
| Review a completed leaf | `$review-work` consumes an explicitly supplied external outcome, checks its artifact/evidence links and resolution-condition coverage, then applies the selected transition. | Complete result resolves the leaf; partial or failed work remains `in-working`; Tech Lead never claims independent verification. |
| React to a contradicting child result | Review marks affected ancestor verdicts and queues early reviews while leaving unrelated sessions untouched. | `review_required` appears before all siblings finish; affected new work is not recommended; no review starts automatically. |
| Complete a parent after several children | Final child resolution queues the parent review; `$review-work` synthesizes all child verdicts. | Parent cannot resolve early; review may resolve, reaffirm, revise, or return it to `in-design`. |
| Add work discovered during review | Tech Lead proposes children and waits for explicit approval, then applies child creation plus the changed parent baseline atomically. | Children begin `in-design`; refusal creates nothing and leaves the parent review pending. |
| Recommend one or several next actions | `$work-log next` interprets state, signed start conditions, coordination notes, findings, and active sessions. | Output contains `(action, work item)` pairs, reasons, context entry points, and a justified parallel grouping without dependency edges. |
| Validate review context links | Helper checks local files, workspace-link paths, and anchors; Tech Lead checks required external URLs when permitted. | Broken required links block transition; unrelated transitive documents are not crawled. |
| Handle concurrent Tech Lead sessions | Every mutation uses the project lock, precondition re-read, overlay validation, safe replacement, and rollback; readers respect an active writer. | Simultaneous ID allocation cannot collide and a reader never reports a partially rolled-up state. |
| Preserve terminal history | Validator prevents unresolved descendants or new children under `resolved`; later work links the old item from an open ancestor or new project. | No `resolved` item transitions backward. |
| Keep Git optional and state clean | All behavior uses current files; ignore/index checks protect local artifacts; no operation stages or commits. | Complete scenario passes outside a Git repository and produces no Git side effects inside one. |
| Preserve provider parity | Claude and Codex adapters execute the same fixture narratives against the same helper. | Their canonical project trees and transition outcomes are semantically equivalent. |

## 3. Test and release gates

The implementation is complete only when all of these layers pass:

1. **Unit tests:** frontmatter, closed schemas, slug and ID allocation, root
   resolution, registry repair, Markdown/anchor parsing, state invariants,
   writer locking, rollback, and Git-index safety.
2. **Protocol conformance fixtures:** every use case in the matrix, including
   negative fixtures for ambiguous attachment, broken links, role reuse,
   premature parent resolution, invalid revision chains, resolved-parent child
   creation, and concurrent ID allocation.
3. **Skill contract tests:** exactly three user-facing skills per provider, no
   agents or hooks, explicit activation language, human checkpoints, and no
   implementation or verification delegation.
4. **Packaged-helper tests:** the copied validator and mutation helper run from
   each installable artifact without importing the source tree.
5. **Native end-to-end trial:** initialize two projects, attach multiple
   worktrees, review and sign a root, run parallel external sessions, record a
   contradictory result, complete all children, run the parent review, and
   resume a recorded session.
6. **Provider-parity gate:** repeat the same narrative in Claude Code and Codex
   and compare the resulting canonical state.
7. **Documentation gate:** update README, installation instructions, examples,
   and upgrade diagnostics; remove all references to the old orchestrator,
   graph states, delegated agents, and pivot workflow.
