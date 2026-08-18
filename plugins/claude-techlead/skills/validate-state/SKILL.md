---
name: validate-state
description: Mechanically validate a repository's .techlead protocol records, IDs, lifecycle states, graph links and backlinks, references, overview provenance, frontier projection, and verification coverage. Use when a user asks to validate, diagnose, inspect, or troubleshoot Tech Lead Agent project state.
---

# Validate project state

Run the packaged, dependency-free validator against the current project:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/techlead-state" validate "${CLAUDE_PROJECT_DIR}"
```

Use `--format json` when structured output will make diagnosis clearer. Report
each issue with its file, code, and invariant. Distinguish mechanical corruption
from semantic questions the validator intentionally cannot decide.

Validation is read-only. Do not edit project state unless the user also asks for
a repair. If repair is requested, preserve immutable referenced records and
rerun validation after the smallest coherent correction.
