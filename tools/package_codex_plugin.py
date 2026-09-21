#!/usr/bin/env python3
"""Build a deterministic Codex plugin ZIP and SHA-256 sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import zipfile

from sync_claude_plugin import CODEX_PLUGIN_ROOT, sync


def plugin_version() -> str:
    manifest = json.loads((CODEX_PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))
    return manifest["version"]


def build_archive(output: Path) -> tuple[Path, str]:
    stale = sync(check=True)
    if stale:
        raise RuntimeError("packaged plugins are stale; run tools/sync_claude_plugin.py")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(
        path for path in CODEX_PLUGIN_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in files:
            relative = Path("codex-techlead") / source.relative_to(CODEX_PLUGIN_ROOT)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            permissions = 0o755 if source.stat().st_mode & stat.S_IXUSR else 0o644
            info.external_attr = (stat.S_IFREG | permissions) << 16
            archive.writestr(info, source.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = output.with_suffix(output.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return sidecar, digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist") / f"techlead-codex-{plugin_version()}.zip",
    )
    parser.add_argument("--expected-version")
    args = parser.parse_args(argv)
    version = plugin_version()
    if args.expected_version and args.expected_version != version:
        parser.error(f"expected version {args.expected_version}, plugin declares {version}")
    sidecar, digest = build_archive(args.output)
    print(f"archive: {args.output}")
    print(f"sha256: {digest}")
    print(f"sidecar: {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
