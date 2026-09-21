# Tech Lead State Protocol 2.0

This protocol defines the provider-neutral work log used by the Tech Lead
design-review workflow. It records signed semantic baselines, current work-item
state, resumable external sessions, and parent roll-up. It does not orchestrate
implementation or independently verify implementation correctness.

## Encoding

Canonical records are UTF-8 Markdown with a deterministic YAML-frontmatter
subset: top-level mappings, scalar values, JSON-style inline values, and scalar
block lists. Nested YAML mappings, anchors, tags, block scalars, and implicit
dates are not supported. The Markdown body remains human-owned and free-form.

Only `PROJECT.md` declares `protocol_version: "2.0"`. Record kinds are inferred
from canonical paths. Frontmatter schemas are closed and live in
[`../schemas`](../schemas).

## Canonical project layout

```text
<descriptive-project-name>/
├── PROJECT.md
├── work-items/
│   └── WI-001-descriptive-title/
│       ├── WORK.md
│       └── revisions/
│           └── r1-descriptive-baseline.md
├── sessions/
│   └── SES-001-descriptive-session.md
├── local/                 # ignored machine-local mappings and writer lock
└── workspace-links/       # ignored symlinks to attached workspaces
```

The project directory is the canonical log root. An attached workspace exposes
it through an ignored `.techlead` symlink and carries a portable
`.techlead-project` locator containing one logical workspace ID and one or more
project UUIDs.

## Records

`PROJECT.md` contains exactly `protocol_version`, `project_id`, `title`,
`root_work_item`, and `workspace_ids`. A project has exactly one root.

Each `WORK.md` contains exactly `id`, `title`, `work_type`, `state`, `parent`,
`active_revision`, and `review_required`. Work types are `design`,
`exploration`, `implementation`, and `verification`. States are `in-design`,
`in-working`, and `resolved`. Every non-root item has exactly one parent.

Each immutable revision contains exactly `revision`, `title`, and `supersedes`.
Its body is the self-contained signed semantic baseline. `r1` supersedes
`null`; every later revision supersedes the preceding revision. Descriptive
revision filenames use `rN-description.md`.

Each live session contains `session`, `provider`, `provider_session_id`, `role`,
`status`, `work_items`, and `workspace_id`, plus optional `git_branch` and
`git_revision`. Roles are `design`, `exploration`, `implementation`,
`verification`, and `techlead-review`; status is `active` or `paused`. Closing a
session removes its live file after compact provenance has been written to its
work items.

## State and revision invariants

- `in-design` has `active_revision: null` and `review_required: false`.
- `in-working` names an existing active revision and may require review.
- `resolved` names an existing active revision, never requires review, has
  only resolved children, accepts no new children, and is terminal.
- Initial sign-off creates `r1` and moves the item to `in-working`.
- A later revision is created only when the signed semantic baseline changes.
  Editorial rewrites, reaffirmation, and resolution retain the active revision.
- A material child contradiction sets `review_required: true` on affected
  `in-working` ancestors immediately. Ordinary parent completion sets the flag
  when every current child is resolved.
- Only an explicitly invoked review applies a work-item state transition.

## Links and workspaces

Context is linked rather than copied. Cross-workspace links use ordinary
Markdown paths through `workspace-links/<workspace-id>/...`. Deterministic
validation checks local targets, declared workspace membership, and heading
anchors. The active review checks external URLs when host permissions allow it
and blocks a transition when a required source is unavailable.

Workspace IDs are stable across clones and worktrees. A provider-neutral local
registry maps project UUIDs to canonical project paths. Registry paths,
attachment mappings, `.techlead` symlinks, `workspace-links`, locks, and
generated snapshots are local state and must never be committed.

## Mutation and authority boundary

Canonical mutations use a project-local single-writer lock, re-read
preconditions, validate a complete staged result, replace files safely, and
roll back on failure. Concurrent writing from different machines is outside
Protocol 2.0.

The deterministic helper validates and applies a semantic decision supplied by
Tech Lead and the human. It does not decide whether assumptions are acceptable,
alternatives are sufficiently covered, evidence is persuasive, a result is
correct, or work is safe to parallelize. Git is optional; protocol operations
never stage or commit files.
