---
name: create-work-item
description: Explicitly create one unsigned child in a Tech Lead Protocol 2.0 work log. Use only when the human directly invokes /create-work-item and names the parent for the new work.
compatibility: Requires Kiro IDE or Kiro CLI v3 and Python 3.10 or newer.
---

# Create a work item

This is a manual-only workflow. If the human did not directly invoke
`/create-work-item`, do not create or mutate a work item; ask them to invoke the
skill explicitly.

From this skill directory, read `references/create-work-item.md` and
`references/PROTOCOL.md`. Run the packaged helper with a Python 3.10+
interpreter as `python3 scripts/techlead-state` (or the platform-equivalent
Python 3 command).

Resolve the canonical project, confirm one explicit parent, and reject a
resolved parent. Prepare a concise free-form body with narrow Markdown links to
the relevant parent context and presumptions. Invoke `create-work-item` with the
requested title and work type.

The child must remain `in-design`, with no active revision and no inherited
sign-off. Validate the project and return the new `WORK.md` as the agent context
entry point.
