# Tech Lead Agent

A local-first technical-lead workflow for long-running engineering projects.

The repository is implementing the design in [`.designs/vision.md`](.designs/vision.md)
and [`.designs/high-level-design.md`](.designs/high-level-design.md). The first
vertical slice is the provider-neutral `.techlead/` state protocol and its
deterministic validator.

## Validate a project

```sh
tools/techlead-state validate /path/to/project
```

The command has no third-party runtime dependencies. See
[`core/protocol/PROTOCOL.md`](core/protocol/PROTOCOL.md) for the record contract.

## Development checks

```sh
python3 -m unittest discover -v
```

The conformance suite materializes complete graph-expansion, resolution-release,
and pivot-reconciliation snapshots and validates them through the public CLI.
