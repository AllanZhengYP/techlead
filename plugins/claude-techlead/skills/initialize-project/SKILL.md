---
name: initialize-project
description: Initialize a repository as a durable Tech Lead Agent project or adopt existing .techlead state. Use when a user asks to start, initialize, onboard, or resume management of a substantial engineering goal in a repository that may not yet contain valid tech-lead project memory.
---

# Initialize a tech-led project

Establish the smallest valid project memory that preserves human intent and
makes the first risk-reducing action explicit.

1. Resolve the repository root. Read applicable `CLAUDE.md`, `AGENTS.md`, and
   nested repository guidance before writing state.
2. Read `${CLAUDE_PLUGIN_ROOT}/core/protocol/PROTOCOL.md`.
3. If `.techlead/` already exists, run:

   ```sh
   "${CLAUDE_PLUGIN_ROOT}/bin/techlead-state" validate "${CLAUDE_PROJECT_DIR}"
   ```

   Adopt valid state. Do not overwrite it. Reconcile human edits and report any
   semantic contradiction that cannot be repaired mechanically.
4. For a new project, derive the charter from the user's goal and repository
   evidence. Separate human-authoritative intent from assumptions, risks,
   decisions, and derived implementation knowledge.
5. Use the templates under `${CLAUDE_PLUGIN_ROOT}/core/templates/` to create the
   five root records and a flat `work-items/` directory. Remove every template
   placeholder before continuing.
6. Create only the few rough work items currently justified. Prefer a `READY`
   research or feasibility item when an architecture, integration, or
   build-versus-adopt choice could invalidate later implementation. Keep
   downstream items `DRAFT` or `BLOCKED` until their contracts are knowable.
7. Give every non-draft item an immutable `r1` assignment contract with explicit
   criteria and criterion-level verification methods.
8. Validate the resulting project. Do not hand off invalid state.

Finish by explaining the charter, highest risks, active frontier, and next
recommended action. Initialization records a plan; it does not claim that any
engineering outcome is already resolved.
