---
name: work-log
description: Explicitly initialize, attach, inspect, validate, manage resumable sessions, or recommend next actions from a Tech Lead Protocol 2.0 work log. Use only when the human directly invokes /work-log for one of those operations.
compatibility: Requires Kiro IDE or Kiro CLI v3 and Python 3.10 or newer.
---

# Manage the work log

This is a manual-only workflow. If the human did not directly invoke
`/work-log`, do not mutate or interpret the Tech Lead work log; ask them to
invoke the skill explicitly.

From this skill directory, read `references/work-log.md` and
`references/PROTOCOL.md`. Route deterministic actions through the packaged
helper using a Python 3.10+ interpreter as `python3 scripts/techlead-state` (or
the platform-equivalent Python 3 command). Never use this skill to transition
work-item state.

For `next`, load the deterministic projection and then inspect the signed start
conditions, current findings, coordination context, and live sessions. Return
one or more `(action, work item)` pairs, each with its `WORK.md` entry point and
reason. Explain why any parallel group is non-colliding; do not invent
dependency edges.

For Kiro CLI session registration, use provider `kiro-cli` and the exact
`sess_<UUID>` ID reported by `/session-id`; never invent a provider session ID.

Keep `.techlead` symlinks, workspace links, local mappings, locks, and snapshots
untracked. Git branch and revision are optional session hints. Never stage or
commit files.
