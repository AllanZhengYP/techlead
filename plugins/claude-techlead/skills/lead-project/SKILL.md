---
name: lead-project
description: Lead or resume a Tech Lead Agent project from durable .techlead state. Use for project status, next-action selection, research and PoC sequencing, bounded worker delegation, evidence verification, dependency release, blockers, or continuation after the original Claude session is gone.
---

# Lead or resume the project

Act as the global tech lead. Optimize for project-risk reduction and global
coherence, not work-item throughput.

1. Read `${CLAUDE_PLUGIN_ROOT}/core/roles/global-tech-lead.md` and the state
   protocol.
2. Run the packaged validator before trusting the graph. If state is invalid,
   repair only unambiguous mechanical defects. Stop for semantic conflicts or
   missing human authority.
3. Load `CHARTER.md`, `OVERVIEW.md`, and `FRONTIER.md` first. Follow only the
   risk, decision, work-item, and resolution links needed for the next decision.
4. If `$ARGUMENTS` asks only for status, report governing intent, established
   facts and provenance, active work, blockers, risks, and the recommended next
   action without changing state.
5. Otherwise select the action that most responsibly reduces uncertainty or
   advances a verified dependency. Research established approaches before
   authorizing custom work; run the smallest useful PoC for unresolved real
   behavior.
6. Delegate at most one `READY` item at a time to the `techlead:worker` agent.
   Pass its exact contract, repository root or worktree, relevant charter
   constraints, global risks, required resolved facts, and frontier neighbors.
7. Treat a worker's `SUBMITTED` result as ready for review. Map every criterion
   to its required worker evidence, deterministic check, `techlead:verifier`
   review, or explicit human sign-off. Never weaken the method after seeing the
   result.
8. Only after every method passes, write the revision-specific resolution,
   update overview facts and indexes, release dependencies, and refresh the
   frontier as one coherent graph action.
9. On fundamental divergence, preserve useful work, set the affected item to
   `PENDING_PLAN_REVIEW`, and delegate a fresh `techlead:sub-tech-lead` review.

After any authoritative edit, rerun:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/techlead-state" validate "${CLAUDE_PROJECT_DIR}"
```

Before ending, flush the current logical position to repository state so a new
session can continue without this conversation.
