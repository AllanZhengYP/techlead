# Tech Lead Agent

A local-first technical-lead workflow for long-running engineering projects.

The repository is implementing the design in [`.designs/vision.md`](.designs/vision.md)
and [`.designs/high-level-design.md`](.designs/high-level-design.md). The first
vertical slice is the provider-neutral `.techlead/` state protocol and its
deterministic validator, packaged in a Claude Code plugin.

## Install in Claude Code

The GitHub marketplace path works with plugin-capable Claude Code versions and
is the primary development and compatibility channel:

```sh
claude plugin marketplace add AllanZhengYP/techlead
claude plugin install techlead@techlead --scope user
```

Pin the marketplace to a release tag when reproducibility matters:

```sh
claude plugin marketplace add AllanZhengYP/techlead@v0.1.0
```

Tagged GitHub Releases also publish `techlead-claude.zip`, its SHA-256 checksum,
and `techlead-claude-marketplace.json`. Claude Code 2.1.224 or newer can install
that archive-backed marketplace without Git:

```sh
claude plugin marketplace add \
  https://github.com/AllanZhengYP/techlead/releases/latest/download/techlead-claude-marketplace.json
claude plugin install techlead@techlead-release --scope user
```

The installed plugin provides `/techlead:initialize-project`,
`/techlead:lead-project`, `/techlead:reconcile-pivot`, and
`/techlead:validate-state`, plus native worker, verifier, and sub-tech-lead
agents.

## Validate a project

```sh
tools/techlead-state validate /path/to/project
```

The command has no third-party runtime dependencies. See
[`core/protocol/PROTOCOL.md`](core/protocol/PROTOCOL.md) for the record contract.

## Development checks

```sh
python3 tools/sync_claude_plugin.py --check
python3 -m unittest discover -v
claude plugin validate plugins/claude-techlead
claude plugin validate .
```

The conformance suite materializes complete graph-expansion, resolution-release,
and pivot-reconciliation snapshots and validates them through the public CLI.

After changing `core/`, the validator, or conformance fixtures, run
`python3 tools/sync_claude_plugin.py` to refresh the self-contained plugin copy.
For local adapter testing, start Claude Code with:

```sh
claude --plugin-dir ./plugins/claude-techlead
```
