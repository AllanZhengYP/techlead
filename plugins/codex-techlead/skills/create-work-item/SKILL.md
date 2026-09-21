---
name: create-work-item
description: Explicitly create one unsigned child in a Tech Lead Protocol 2.0 work log. Use only when the human invokes $create-work-item and names the parent for the new work.
---

# Create a work item

Resolve this skill's installed plugin root, then read
`core/behaviors/create-work-item.md` and `core/protocol/PROTOCOL.md` from that
root. Use the packaged `bin/techlead-state` helper.

Resolve the canonical project, confirm one explicit parent, and reject a
resolved parent. Prepare a concise free-form body with narrow Markdown links to
the relevant parent context and presumptions. Invoke `create-work-item` with the
requested title and work type.

The child must remain `in-design`, with no active revision and no inherited
sign-off. Validate the project and return the new `WORK.md` as the agent context
entry point.
