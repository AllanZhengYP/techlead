#!/usr/bin/env python3
"""Build a deterministic Claude Code plugin ZIP and SHA-256 sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import zipfile

from sync_claude_plugin import PLUGIN_ROOT, sync


def plugin_version() -> str:
    manifest = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    return manifest["version"]


def build_archive(output: Path) -> tuple[Path, str]:
    stale = sync(check=True)
    if stale:
        raise RuntimeError("packaged plugin is stale; run tools/sync_claude_plugin.py")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(
        path for path in PLUGIN_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in files:
            relative = Path("techlead") / source.relative_to(PLUGIN_ROOT)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = source.stat().st_mode
            permissions = 0o755 if mode & stat.S_IXUSR else 0o644
            info.external_attr = (stat.S_IFREG | permissions) << 16
            archive.writestr(info, source.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = output.with_suffix(output.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return sidecar, digest


def write_release_marketplace(output: Path, *, archive_url: str, digest: str) -> None:
    payload = {
        "$schema": "https://json.schemastore.org/claude-code-marketplace.json",
        "name": "techlead-release",
        "owner": {"name": "Tech Lead Agent contributors"},
        "metadata": {"description": "Release artifacts for Tech Lead Agent"},
        "plugins": [
            {
                "name": "techlead",
                "source": {
                    "source": "archive",
                    "url": archive_url,
                    "sha256": digest,
                },
                "description": (
                    "Maintain durable project intent, work graphs, evidence, verification, and pivots."
                ),
                "category": "development",
                "tags": ["engineering", "planning", "agents"],
            }
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist") / f"techlead-claude-{plugin_version()}.zip",
    )
    parser.add_argument("--expected-version", help="fail unless plugin.json has this version")
    parser.add_argument("--release-marketplace-output", type=Path)
    parser.add_argument("--archive-url")
    args = parser.parse_args(argv)
    if bool(args.release_marketplace_output) != bool(args.archive_url):
        parser.error("--release-marketplace-output and --archive-url must be provided together")
    version = plugin_version()
    if args.expected_version and args.expected_version != version:
        parser.error(f"expected version {args.expected_version}, plugin declares {version}")
    sidecar, digest = build_archive(args.output)
    if args.release_marketplace_output:
        write_release_marketplace(
            args.release_marketplace_output,
            archive_url=args.archive_url,
            digest=digest,
        )
    print(f"archive: {args.output}")
    print(f"sha256: {digest}")
    print(f"sidecar: {sidecar}")
    if args.release_marketplace_output:
        print(f"marketplace: {args.release_marketplace_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
