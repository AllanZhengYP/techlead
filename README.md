# Tech Lead Agent

A local-first design-review bar-raiser and durable work-item log for Codex and
Claude Code. Tech Lead is explicitly invoked; implementation and independent
verification remain in the user's tools and sessions of choice.

The product behavior is defined by the [vision](.designs/vision.md),
[high-level design](.designs/high-level-design.md), and
[low-level design](.designs/low-level-design.md). Both provider plugins use the
same dependency-free [Protocol 2.0](core/protocol/PROTOCOL.md) engine.

## Capabilities

Both adapters expose exactly three capabilities:

- `review-work`: bar-raise an `in-design` item, assess a supplied `in-working`
  outcome, or synthesize child verdicts;
- `create-work-item`: create one unsigned child beneath an explicit parent; and
- `work-log`: initialize or attach projects, inspect status, manage resumable
  sessions, validate state, and recommend next actions.

Codex invokes them as `$review-work`, `$create-work-item`, and `$work-log`.
Claude Code invokes `/techlead:review-work`, `/techlead:create-work-item`, and
`/techlead:work-log`. Implicit invocation is disabled.

## Plugin artifacts

The Claude Code adapter is available through the repository marketplace:

```sh
claude plugin marketplace add AllanZhengYP/techlead
claude plugin install techlead@techlead --scope user
```

The Codex adapter is the portable plugin at `plugins/codex-techlead`; add it to
the desired personal, repository, or team marketplace when testing locally.
Tagged releases publish deterministic `techlead-claude.zip` and
`techlead-codex.zip` archives with SHA-256 sidecars. The Claude release also
includes its archive-backed marketplace descriptor.

## Initialize and inspect a project

```sh
tools/techlead-state init \
  --control-dir /path/to/techlead-control \
  --name session-platform-modernization \
  --title "Session platform modernization" \
  --root "Session platform design" \
  --workspace /path/to/service-workspace \
  --workspace-id service-a

tools/techlead-state status /path/to/service-workspace
tools/techlead-state next /path/to/service-workspace
tools/techlead-state validate /path/to/service-workspace
```

The canonical project is a descriptive directory under the selected control
root. An attached worktree receives a local `.techlead` symlink and a portable
`.techlead-project` locator. The helper never stages or commits files; local
symlinks, mappings, locks, and workspace links are excluded from Git.

Use the explicit provider skill for semantic review. The deterministic
`apply-review` command exists for the skill to persist a human-authorized
decision; it does not decide whether a design or result is acceptable.

## Development checks

```sh
python3 tools/sync_claude_plugin.py --check
python3 -m unittest discover -v
python3 /path/to/plugin-creator/scripts/validate_plugin.py plugins/codex-techlead
claude plugin validate plugins/claude-techlead
```

After changing `core/`, `tools/techlead_state/`, or conformance fixtures, run:

```sh
python3 tools/sync_claude_plugin.py
```

Despite its historical filename, that command synchronizes the shared core into
both provider plugins. Package release artifacts with
`tools/package_claude_plugin.py` and `tools/package_codex_plugin.py`.
