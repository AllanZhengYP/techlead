# Tech Lead Agent — High-Level Design

> **Status:** Approved
> **Date:** 21 September 2026
> **Depends on:** [Vision](./vision.md)

## 1. Design decisions

The project ships as two installable, versioned plugins:

1. a Codex plugin;
2. a Claude Code plugin.

They implement one shared workflow and repository-state contract but use the native extension and agent-invocation mechanisms of each host. A plugin is the distribution package; Codex or Claude Code remains the runtime.

The PoC does not ship a service, daemon, database, scheduler, or custom agent loop. It also does not require an MCP server. The harnesses already provide the local model loop, repository tools, shell and Git access, isolated agent contexts, permission handling, session interaction, and human steering needed to test the vision.

## 2. What we ship

The product is the plugin pair, not a new coding harness. A release contains:

- one installable Codex plugin;
- one installable Claude Code plugin;
- a versioned, provider-neutral `.techlead/` state protocol shared by both;
- deterministic validation code and conformance fixtures embedded in each plugin;
- documentation and a small example project demonstrating the full PoC workflow.

The two plugins should normally share a release version. Each initialized project records its state-protocol version so a plugin can reject an incompatible project or perform an explicit migration rather than reinterpret old records silently.

The source repository produces two self-contained plugin artifacts from a shared semantic core:

```text
techlead-agent/
├── core/
│   ├── behaviors/             # provider-neutral review and work-log behavior
│   ├── protocol/              # work-item tree and state semantics
│   ├── templates/             # .techlead project templates
│   └── schemas/               # mechanically checkable record shapes
├── plugins/
│   ├── codex-techlead/
│   │   ├── .codex-plugin/plugin.json
│   │   └── skills/
│   └── claude-techlead/
│       ├── .claude-plugin/plugin.json
│       └── skills/
└── tools/
    └── techlead-state         # local deterministic helper
```

The release process copies or generates shared material into each plugin artifact. Installed plugins must be self-contained; they must not depend on paths back into this source tree.

The normal delivery path is the native marketplace or plugin-install mechanism of each host. Local-directory installation remains supported for development. Installing the plugin does not install a daemon, start a process, or rewrite the user's global agent configuration.

### User-facing capabilities

Each plugin provides the same conceptual entry points, even if their host-specific invocation names differ:

- **Initialize or adopt a project:** create or validate the canonical Tech Lead log and its portable project identity.
- **Review work:** explicitly conduct the state-appropriate review for a named
  work item: bar-raise an `in-design` definition, evaluate an `in-working`
  outcome, or synthesize child findings.
- **Create a work item:** explicitly create a child from a named parent and populate links to inherited context and presumptions.
- **Manage the work log:** inspect status, register or update sessions, and
  recommend the next one or more compatible `(action, work item)` pairs without
  performing a state transition.
- **Attach a workspace:** associate a local workspace or worktree with the canonical log without committing a symlink or snapshot. This remains available for setup without an agent session.
- **Validate state:** mechanically check record shape, IDs, parent/child links, and references.

Review, child creation, and next-work recommendation are agent skills.
Attachment, session bookkeeping, status projection, and state validation use
deterministic local operations. The helper does not independently schedule work
or decide project meaning.

Invocation stays concise and host-native. Codex uses explicit skill mentions
such as `$review-work`, `$create-work-item`, and `$work-log`. Claude Code uses
the plugin namespace required by that host, such as
`/techlead:review-work`. Implicit or model-initiated invocation is disabled
for every Tech Lead skill.

### Multi-project control root and attached workspaces

A human-chosen control root may contain several independent Tech Lead project
directories. Each descriptively named project directory is its project's
canonical writable log root; it does not contain another nested `.techlead/`.
Git may version the whole control root or individual project directories when
the human wants audit or transport, but no protocol behavior requires or
creates commits. Implementation and verification workspaces attach to one
project directory rather than maintaining competing copies:

```text
techlead-control/                       # human-chosen multi-project root
├── session-platform-modernization/    # one canonical project log root
│   ├── PROJECT.md
│   ├── work-items/
│   │   └── WI-014-descriptive-title/
│   │       ├── WORK.md
│   │       └── revisions/
│   ├── sessions/                      # SES-NNN descriptive live-session files
│   ├── local/                         # ignored attachment mappings
│   └── workspace-links/               # ignored local symlinks
└── payment-reliability/               # another independent project
    └── ...

implementation-workspace/             # separate Git repository or worktree
├── .techlead-project                  # portable workspace/project IDs
└── .techlead -> /control/session-platform-modernization
```

`$work-log init --control-dir <path> --name <descriptive-kebab-name> ...` is
the sole project/root creation path. It refuses an existing target directory,
creates the project root and `WI-001` in `in-design`, attaches the current
workspace, and makes no Git commit. The project UUID remains authoritative, so
renaming the descriptive directory only requires repairing local mappings.

`initialize-project` generates a UUID `project_id` and stores it in
`PROJECT.md`. Each attached repository has one stable `workspace_id`, shared by
its clones and worktrees when the locator is shared or tracked, and may bind to
several Tech Lead projects:

```yaml
---
workspace_id: service-a
project_ids:
  - 8d96a5d7-4127-4ef5-a3da-32ea927d951f
  - 3a78c921-b65f-4e93-853d-53a49bf36e84
---
```

`.techlead-project` contains no machine-specific path. A local registry maps
each project UUID to its canonical log root. This is one provider-neutral
per-user registry shared by Codex and Claude, stored in the platform's local
user-state location and never committed. `init` registers its new project;
`attach --control-dir <path>` scans that root and registers matching UUIDs on a
new machine. Before following a mapping, the resolver verifies that the target
`PROJECT.md` contains the expected UUID. The ignored `.techlead` symlink is a
per-worktree selection: different worktrees of the same repository may attach
to different listed projects. A command may target a project explicitly
without changing that selection. When several bindings exist and neither a
local selection nor an explicit project identifies one, the helper asks the
human rather than guessing. Moving or renaming a project only requires repairing
the local mapping.

`PROJECT.md` has this complete required frontmatter:

```yaml
---
protocol_version: "2.0"
project_id: 8d96a5d7-4127-4ef5-a3da-32ea927d951f
title: Session platform modernization
root_work_item: WI-001
workspace_ids:
  - service-a
  - web-client
---
```

Its body is optional. `workspace_ids` declares logical repository membership,
not local checkout paths, and may initially be empty.
Machine-specific checkout paths and attachment keys live only under the
project's ignored `local/` directory, visible as `.techlead/local/` from an
attached workspace. There is no portable `workspaces/` registry.
It also names exactly one `root_work_item`, created with the initial design by
`initialize-project`. Every later work item must be created explicitly from an
existing parent. A new unrelated top-level design uses a separate control
project directory under a control root rather than silently adding another
root.

Every non-root item has exactly one decomposition parent. The first protocol
does not define dependency, related, or affects edges between branches. Shared
context and coordination remain part of Tech Lead's design-review judgment and
the signed parent/child content rather than a separate graph ontology.

`$create-work-item` always creates the child with `state: in-design`,
`active_revision: null`, and `review_required: false`. Creation never inherits
the parent's sign-off or silently approves the child. Only an explicit
`$review-work` of that child can establish its first semantic baseline and move
it to `in-working`, even when the parent review already made that review brief.
The command rejects a resolved parent because resolution is terminal.

The `WORK.md` body is human-owned, free-form Markdown. The protocol does not
require named sections, a fixed order, or a template for start conditions and
coordination. During review, Tech Lead must nevertheless locate and evaluate
enough information in the item or its linked context to judge when each child
may start and which children can proceed together. The signed parent revision
records that judgment. Work-log recommendations re-evaluate it against current
child outcomes and live sessions. Deterministic validation checks only the
minimal record envelope and links; it does not require headings or interpret
the prose.

The complete required `WORK.md` frontmatter is intentionally small:

```yaml
---
id: WI-014
title: Session authentication
work_type: design
state: in-working
parent: WI-001
active_revision: r2
review_required: false
---
```

The root uses `parent: null`. `active_revision` is `null` when no signed
revision currently governs the item; historical revisions remain in the
revision directory. `review_required: true` means a mandatory exception or
roll-up review is pending while the active revision still governs. An
`in-design` item already requires review before work may proceed, so it does
not need that flag to say the same thing. Record type comes from the canonical
`work-items/*/WORK.md` location, and protocol version comes from `PROJECT.md`.
No other `WORK.md` frontmatter is required.

There is also no committed project index, overview, or frontier projection.
`techlead-state` derives status, review-due items, and active-session facts by
scanning `WORK.md` and live session frontmatter. Tech Lead combines those facts
with signed start conditions, current findings, and coordination context to
recommend state-aware `(action, work item)` pairs. Actions may be to continue
authoring, invoke `$review-work`, execute signed work, or perform a due parent
review. Parallel recommendations include explicit non-collision reasoning rather
than relying on dependency edges. A mechanical projection may be cached under
the project's ignored `local/` directory, but derived cache data is never
canonical or committed.

The earlier `CHARTER.md`, `OVERVIEW.md`, `FRONTIER.md`, `RISKS.md`, and
`DECISIONS.md` records are not part of this protocol. `PROJECT.md` holds only
project identity and logical workspace definitions. Design intent remains in
linked source documents; assumptions, alternatives, and accepted decisions are
captured by signed revisions; current risks and review findings live in
`WORK.md`; active work comes from session links; and resolved child outcomes
feed linked parent verdicts.

`techlead-state attach` resolves the mapping and may create or repair an
absolute `.techlead` symlink. All plugin behavior resolves the canonical root
through the helper instead of assuming that `$PWD/.techlead` is a real
directory. The symlink is a local convenience, not protocol state.

Workspace attachments and agent sessions are separate records. One attached
workspace may host many sessions, an attachment may exist without a session,
and a session may move between workspace instances. The normal registration UX
combines their creation atomically: `work-log register-session` first attaches
or repairs the supplied workspace, then registers the provider, opaque session
ID, role, work item, and current workspace attachment. A later handoff
preserves the session ID and updates the local workspace mapping. Git branch
and revision may be recorded when useful, but neither is required.

`sessions/` contains one mutable file per active or resumable session, named
`SES-NNN-<descriptive-title>.md`. The stable internal `SES-NNN` identity avoids
provider-ID collisions and unsafe filename characters; the record separately
stores the provider's opaque resumable ID. A session may link several work
items, which is why it is not embedded in one `WORK.md`. It stores no transcript,
result body, absolute path, credential, or repository snapshot. When a session
is no longer resumable, its live file is removed and affected work items retain
compact provenance in their free-form bodies: the internal `SES-NNN`, provider,
and opaque provider session ID. This keeps the reference useful after the live
session file is removed without depending on Git history.

The complete required session frontmatter is:

```yaml
---
session: SES-003
provider: codex
provider_session_id: 019f...
role: implementation
status: active
work_items:
  - WI-016
workspace_id: service-a
---
```

Optional `git_branch` and `git_revision` fields are portable resumption hints.
The local worktree name and absolute path live only in an ignored mapping such
as `.techlead/local/sessions/SES-003.yaml`. A stale or missing local mapping
causes a repair warning, not an invalid session record. The session body is
optional and may contain only a concise resumption note. `role` is one of
`design`, `exploration`, `implementation`, `verification`, or
`techlead-review`. `status` is `active` or `paused`; permanently closed sessions
have no live session file.

The project log maintains an ignored local link-farm under `workspace-links/`
(visible as `.techlead/workspace-links/` from an attached workspace). Each
logical workspace ID points to its currently attached local checkout.
Cross-workspace references are ordinary canonical Markdown links whose path
encodes both the workspace ID and repository-relative path:

```markdown
[Session design](../../workspace-links/service-a/docs/session-authentication.md)
```

An optional Git revision may appear beside the link as supporting provenance.
The validator recognizes this path form, verifies project membership, and
checks the target when the workspace is attached. There is no duplicate YAML
reference object or required body heading.

The plugin never stages or commits files. An attachment symlink, workspace-link
symlink, generated `.techlead` snapshot, or machine-local mapping must never be
committed. Relevant ignore rules are installed, attachment refuses to replace
tracked content, and validation fails if any such artifact is present in a Git
index. The portable project locator and canonical log may be committed manually
when the human wants portability or history, but protocol behavior never
depends on a commit being present.

Canonical mutations use a local single-writer transaction. The helper acquires
an ignored `<project-root>/local/` lock, re-reads current state, applies the complete
mutation and recursive roll-up, validates the result, writes atomically, and
then releases the lock. A competing writer reports the owning operation instead
of guessing or overwriting it. Stale-lock recovery is explicit. Read-only
projection does not take the lock. This coordinates sessions sharing one local
canonical root; cross-machine concurrent writing is outside the PoC.

This design supports multiple local workspaces and Git worktrees that can reach
the same filesystem path. A remote, containerized, or differently sandboxed
workspace may require an explicitly generated read-only context export, but
such an export is ephemeral and must never be committed as project state.

## 3. Actor and authority model

The product ships one agent role: **Tech Lead**. Implementation and
verification are external activities whose sessions and results may be linked
into the work-item log.

| Actor | Responsibility | Relationship to the plugin |
| --- | --- | --- |
| Human design owner | Author the design, make consequential decisions, disposition assumptions and alternatives, choose tools, and explicitly invoke Tech Lead. | Owns design authority and controls activation. |
| Tech Lead | Adversarially review named design documents, sign off revisions, maintain work-item records, roll up results, and recommend next work. | The only shipped agent role. |
| External implementer | Produce an implementation result and evidence using Codex, Claude Code, Pi, another tool, or a human workflow. | Independent of the plugin; optionally registered by provider and session ID. |
| External verifier | Independently evaluate an implementation or claim and report evidence. | Independent of the plugin; optionally registered by provider and session ID. |

Tech Lead does not spawn, steer, wait for, stop, or impersonate implementation
or verification sessions. It may record their opaque session references and
explicitly supplied results. Implementation and verification remain usable when
the Tech Lead plugin is absent or inactive.

## 4. Harness and external-tool boundary

The plugins should use host capabilities instead of reproducing them:

| Concern | Plugin responsibility | Host or external-tool responsibility |
| --- | --- | --- |
| Tech Lead behavior | Supply design-review and work-log instructions plus selected linked context. | Run the Tech Lead model/tool loop when explicitly invoked. |
| External execution | Record a session reference or result when explicitly supplied. | Let the human start, steer, pause, resume, and stop implementation or verification sessions. |
| Context entry | Resolve the canonical log, maintain `WORK.md` as a linked entry point, and record the signed revision. | Let an external session follow the links it needs through an attached workspace. |
| Repository operations | Maintain `.techlead/` records and state the expected artifact or evidence references. | Provide file, search, shell, Git, and other tools to the active session. |
| Workspace isolation | Record relevant workspace or revision references when supplied. | Provide worktree or other isolation to the external session when desired. |
| Permissions | Express project authority boundaries and protected actions. | Enforce sandbox, tool approvals, credentials, and user consent. |
| Human checkpoints | Ask review questions with recommendations and wait for human dispositions. | Display the question and resume the explicitly invoked Tech Lead session. |
| Session continuity | Record provider, opaque session ID, role, and status. | Preserve and resume the referenced session when supported. |
| Workspace attachment | Maintain the portable project locator, local root mapping, and ignored convenience symlink. | Provide a local workspace or worktree with filesystem access to the canonical root. |
| Durable memory | Maintain `.techlead/` records and evidence links. | Preserve ordinary files; optionally use Git for human-controlled history or transport. |

This boundary keeps provider adapters thin. The project does not parse model
transcripts, simulate a message loop, maintain its own approval UI, launch a
worker fleet, or infer completion from process exit alone.

## 5. Explicitly invoked interaction flow

The plugin has no continuous coordinator and no child-agent topology. Tech Lead
runs only when the human explicitly invokes review-work, child creation, or
work-log behavior.

### Review a work item

1. The human invokes `$review-work` with a named work item and supplies any new
   outcome or evidence to consider. The skill registers the current provider
   session as `techlead-review`, or reuses its existing `SES-NNN` and adds the
   item. When the host cannot expose its opaque session ID, Tech Lead asks the
   human for it once.
2. A provider session already registered as `design`, `exploration`,
   `implementation`, or `verification` is never relabeled. Tech Lead asks the
   human to switch to a dedicated review session instead. One dedicated review
   session may review many items and may attach or repair its current workspace
   during registration.
3. The host loads normal repository guidance; Tech Lead opens the item's
   `WORK.md` and follows its source, parent, assumption, decision, and evidence
   links as needed.
4. Before transitioning the item, Tech Lead validates every link directly in
   `WORK.md`, the named design document, the active revision, and each document
   it opens or relies on during the review. Local and cross-workspace targets
   must exist and heading anchors must resolve. External URLs are checked when
   network access is available; an unavailable required source blocks the
   transition. The review does not recursively crawl documents it did not open
   or rely on.
5. Tech Lead chooses the review bar from the current state. For `in-design`, it
   adversarially reviews assumptions, alternatives, requirements,
   decomposition, and verifiable outputs. For an `in-working` leaf, it records
   the supplied outcome and assesses coverage of the signed resolution
   conditions without independently verifying correctness. For an
   `in-working` parent, it synthesizes the required child outcomes. A resolved
   item is terminal and is not reviewed into another state.
6. Tech Lead explains its recommendation and obtains human decisions where
   materiality or invalidation is uncertain. The deterministic helper then
   applies the authorized transition and recursive roll-up atomically.
7. An initial sign-off or a successful review that changes the signed semantic
   baseline writes an immutable, descriptively named revision. Reaffirmation or
   resolution under the existing baseline keeps `active_revision` unchanged.
   An incomplete review records current findings without advancing state.

When review identifies additional child work, Tech Lead presents the proposed
children and may create them within the same review only after explicit human
confirmation. The creation operation remains the same: each child starts
`in-design` with no active revision. Child creation and the parent revision are
one atomic mutation. Without explicit approval, no child is created and the
parent remains `in-working` with `review_required: true`.

A revision is a self-contained semantic baseline created when successful
explicit sign-off establishes a different baseline, not a snapshot of every
byte in `WORK.md` and not a receipt for every review. It records the accepted
goal, requirements and boundaries, assumptions and alternatives, required
children, resolution conditions, and review rationale. Source paths, Git
revisions, and content hashes may be retained as supporting provenance, but
they are not prerequisites for review and never determine materiality by
themselves.

The complete required revision frontmatter is `revision`, `title`, and
`supersedes`. The first revision uses `supersedes: null`; later revisions name
the preceding semantic baseline. The containing work-item directory identifies
the owner. Dates, source hashes, Git revisions, and other provenance are
optional.

Tech Lead compares the active semantic baseline with the current free-form
`WORK.md`, linked design context, and relevant child findings. Reformatting,
reordering, or clarifying prose does not require a revision when the signed
meaning is unchanged. Evidence that plausibly contradicts that meaning sets
`review_required: true`; it does not automatically invalidate the parent.
Tech Lead evaluates the full impact and recommends whether to retain, revise,
or abandon the baseline. The human makes the final materiality and invalidation
decision. No pre-review Git commit is required.

Tech Lead does not automatically stage or commit the resulting files. Revision
immutability is a protocol rule enforced by validation; Git history is optional
and never required to interpret current state.

### Use an external implementation or verification session

1. The human chooses an `in-working` item and invokes `work-log
   register-session` with its provider, opaque session ID, role, and workspace.
2. The command atomically attaches or repairs the workspace, records any
   supplied optional Git position, and links the distinct session and
   workspace-attachment records to the work item. Registration is useful for
   resumption and parallel-work recommendations but is not required to execute
   the item.
3. The external session works independently. Tech Lead does not relay tactical
   messages or control its lifecycle.
4. The external session later returns an outcome with artifact and evidence
   links. The human invokes `$review-work` for the producing item; Tech Lead
   records and reviews the supplied outcome without claiming to have
   independently verified it.

### Roll up results

Recording a child result updates linked parent context. A material challenge to
a signed assumption queues an early Tech Lead review and prevents new affected
work from being recommended. When every current child is resolved, the log
queues a completion review. Neither condition starts a Tech Lead session
automatically; the human invokes the review.

The completion review either resolves the parent under its current revision,
reaffirms that revision, signs a changed revision (with any explicitly approved
new children created in the same transaction), or returns the parent to
`in-design`. Existing external sessions remain available for the human to
resume or redirect.

Resolution requires every current child to be resolved and is terminal. Later
discoveries create a new work item under the nearest appropriate unresolved
ancestor and link the resolved item as context. If the root is resolved, the
follow-up starts a new Tech Lead project and links the closed project rather
than rewriting its history.

## 6. Provider adapters

### Codex plugin

The Codex artifact packages Tech Lead review and work-log behavior as skills,
plus templates and deterministic scripts. It does
not package or invoke implementation and verification agents. Codex sessions
used for those activities are external sessions from the protocol's point of
view, even when the same user launches them from Codex.

### Claude Code plugin

The Claude Code artifact packages the same Tech Lead skills, templates, and
deterministic scripts. It does not package
worker, verifier, or sub-tech-lead agent definitions. Claude Code sessions used
for implementation or verification remain independently launched external
sessions whose IDs and results may be recorded in the shared log.

## 7. Hooks and MCP policy

The PoC ships no hooks. `$review-work`, `$create-work-item`, and mutating
`$work-log` actions invoke validation directly and persist each completed
mutation immediately. No hidden or host-specific process runs after ordinary
edits or at session end. Hooks may be reconsidered only after usage identifies
a concrete recurring failure that explicit commands cannot address.

An MCP server is intentionally absent from the PoC. Local files and built-in harness tools are sufficient. MCP becomes justified only if the workflow later needs a stable cross-harness tool API, remote project storage, or external-system integration that cannot be expressed safely through repository files and local scripts.

## 8. Compatibility contract

Provider parity means equivalent outcomes, not identical files or prompts. Both plugins must preserve:

- the canonical project-log format exposed to an attached workspace as
  `.techlead/`;
- work-item states and single-parent decomposition semantics;
- immutable design sign-off and current-review-finding semantics;
- `WORK.md` context-entry and link rules;
- external session and result references;
- parent roll-up and review-trigger behavior;
- next-work eligibility semantics.

Provider-specific behavior is allowed only for invocation, tool and permission
surfaces, session-link affordances, and user-interface presentation.

## 9. Low-level design

The concrete migration plan, implementation phases, use-case acceptance matrix,
and test and release gates are maintained in the
[Low-Level Design](./low-level-design.md). That document implements this
architecture without redefining its product boundaries or protocol semantics.

## 10. PoC implementation decisions

- **Provider order:** Implement the Claude Code plugin first, followed by Codex. The first adapter is a development vehicle, not the semantic reference.
- **User-facing entry points:** Expose only `$review-work`,
  `$create-work-item`, and `$work-log` in Codex. `$work-log` provides explicit
  `init`, `status`, `next`, `attach`, `register-session`, `pause-session`,
  `close-session`, and `validate` actions; it does not transition work-item
  state. Claude Code exposes equivalent names through its required plugin
  namespace.
- **State representation:** Use Markdown records with YAML frontmatter. A
  `WORK.md` frontmatter envelope contains only `id`, `title`, `work_type`,
  `state`, `parent`, `active_revision`, and `review_required`. Its free-form
  body and linked context hold the human-owned substance. Sign-offs that
  establish changed semantic baselines create immutable revision files;
  current findings and outcomes remain in
  `WORK.md` rather than spawning attempt, verification, resolution, or
  invalidation record types.
- **Identifiers and references:** Protocol identity is limited to the project
  UUID, stable `workspace_id`, `WI-NNN`, `SES-NNN`, and the revision identity
  `WI-NNN@rN`. Assumptions, alternatives, evidence, risks, and decisions use
  narrow file-and-heading links rather than separate ID registries. Artifact
  and evidence references may contain repository-relative paths and optional
  Git revisions. Timestamps are informational and never determine correctness.
- **Validation boundary:** Deterministic validation checks exact frontmatter
  schemas, enum values, unique work-item/session/revision identities, the one-root
  acyclic parent tree, revision chains and filenames, locator membership,
  referential integrity, and the prohibition against tracked local attachment
  artifacts. It enforces that `in-design` has no active revision, `in-working`
  and `resolved` name a valid active revision, and `review_required: true`
  appears only while `in-working`. It also rejects unresolved children beneath
  a resolved item and rejects creation under a resolved parent. It does not
  interpret prose or decide
  evidence sufficiency, materiality, alternative coverage, task quality,
  resolution, or parallel-work safety.
- **Workspace isolation:** Tech Lead does not request, create, switch, merge, or
  remove worktrees. The human or external tool chooses isolation. Session
  registration records the supplied workspace and optional Git hints, while
  the deterministic helper only attaches that existing location.
- **Hooks:** Ship no hooks in the PoC. Reconsider them only from observed usage
  after the explicit command workflow is complete.

The `PROJECT.md`, `WORK.md`, revision, and session envelopes are fixed above;
implementation may now translate them directly into validator schemas and
conformance fixtures.

> **Design rule:** Use plugins to install the workflow, repository files to preserve the project, native agents to execute work, and the selected harness to manage sessions, tools, isolation, permissions, and human interaction.
