---
name: reconcile-pivot
description: Reconcile a consequential project pivot across a resolved primary node, descendants, consumers, current facts, decisions, and repository artifacts. Use when new evidence or human direction changes a governing design or assumption after other work has depended on it.
---

# Reconcile a project pivot

Treat the pivot as an ordinary, decomposable revision-transition subproject;
never hide migration work in a metadata-only edit.

1. Read the global tech-lead role and protocol. Validate current state.
2. Identify the pivoted primary node, its authoritative revision, the intended
   target design, the evidence or human decision, and the protected authority
   involved. Stop if any of these is materially ambiguous.
3. Record the pivot decision, move the primary node to `REVISING`, suspend its
   old revision for new dependency releases, and create a normal transition work
   item with `target_node` and `from_revision`.
4. Pause assignments whose governing context may have changed. Delegate a fresh
   `techlead:sub-tech-lead` agent with the complete relevant project view.
5. Traverse decomposition descendants, dependency consumers, related context,
   and artifact links. Classify every reachable affected node as reaffirmed,
   revision required, invalidated, or pending investigation. Continue through
   newly invalidated nodes until no downstream consumer is unreviewed.
6. Decompose the transition only where impact analysis, implementation
   migration, or artifact reconciliation needs independently verifiable work.
   Preserve overlapping valid changes; never restore an old repository snapshot
   blindly.
7. Remove invalidated claims from the current overview while retaining their
   historical resolution entries. Ensure no `READY` item depends on suspended
   or invalidated authority.
8. Verify the reconstructed graph and workspace. Resolve the transition and
   publish the primary node's next revision only after all transition criteria
   and required child work pass.
9. Validate state and summarize the old authority, target revision, affected
   dispositions, preserved work, migration evidence, and residual uncertainty.
