---
name: work-log
description: Explicitly initialize, attach, inspect, validate, manage resumable sessions, or recommend next actions from a Tech Lead Protocol 2.0 work log. Use only when the human asks for one of those log operations.
disable-model-invocation: true
---

# Manage the work log

Read `${CLAUDE_PLUGIN_ROOT}/core/behaviors/work-log.md` and the packaged
protocol. Route deterministic actions to `${CLAUDE_PLUGIN_ROOT}/bin/techlead-state`.
Never use this skill to transition work-item state.

For `next`, load the deterministic projection and then inspect the signed start
conditions, current findings, coordination context, and live sessions. Return
one or more `(action, work item)` pairs, each with its `WORK.md` entry point and
reason. Explain why any parallel group is non-colliding; do not invent
dependency edges.

Keep `.techlead` symlinks, workspace links, local mappings, locks, and snapshots
untracked. Git branch and revision are optional session hints. Never stage or
commit files.
