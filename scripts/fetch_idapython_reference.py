#!/usr/bin/env python3
"""Fetch a pinned IDAPython API reference without vendoring the full SDK.

The official ``apidoc/*.py`` files are documentation stubs, not IDAPython's
implementation. This script clones into a temporary directory and retains only
those stubs, the qualified symbol inventory, and the examples index.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path


DEFAULT_REPOSITORY = "https://github.com/HexRaysSA/ida-sdk.git"
PASS_LINE = re.compile(r"^(?P<indent>\s*)pass(?P<suffix>\s*(?:#.*)?)$", re.MULTILINE)


def run(*arguments: str, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        arguments,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def normalize_stub(source: str, origin: str) -> str:
    source = PASS_LINE.sub(r"\g<indent>...\g<suffix>", source)
    header = f"# Generated from {origin}; documentation stub, not implementation.\n"
    return header + source.rstrip() + "\n"


def fetch(repository: str, ref: str, output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="hexmux-idapython-") as temporary:
        checkout = Path(temporary) / "ida-sdk"
        clone = ["git", "clone", "--depth", "1"]
        if ref:
            clone.extend(("--branch", ref))
        clone.extend((repository, str(checkout)))
        run(*clone)

        commit = run("git", "rev-parse", "HEAD", cwd=checkout)
        root = checkout / "src" / "plugins" / "idapython"
        apidoc = root / "apidoc"
        symbols = root / "api_contents.brief"
        examples_index = root / "examples" / "index.md"
        if not apidoc.is_dir() or not symbols.is_file():
            raise RuntimeError("checkout does not contain the expected IDAPython API specification")

        staging = output.with_name(output.name + ".tmp")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        stubs = staging / "stubs"
        stubs.mkdir()

        count = 0
        for source_path in sorted(apidoc.glob("*.py")):
            destination = stubs / (source_path.stem + ".pyi")
            destination.write_text(
                normalize_stub(
                    source_path.read_text(encoding="utf-8"),
                    f"HexRaysSA/ida-sdk@{commit}:{source_path.relative_to(checkout)}",
                ),
                encoding="utf-8",
            )
            count += 1

        shutil.copyfile(symbols, staging / "symbols.txt")
        if examples_index.is_file():
            shutil.copyfile(examples_index, staging / "examples-index.md")

        manifest = {
            "schema": 1,
            "repository": repository,
            "requested_ref": ref or "HEAD",
            "commit": commit,
            "generated_at": datetime.now(UTC).isoformat(),
            "stub_modules": count,
            "source": "src/plugins/idapython/apidoc",
            "limitations": "Curated apidoc stubs are not the complete generated runtime API.",
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        if output.exists():
            shutil.rmtree(output)
        staging.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPOSITORY, help="Git repository URL or local path")
    parser.add_argument("--ref", default="", help="release tag or branch, such as v9.3.0-release")
    parser.add_argument("--output", type=Path, required=True, help="destination reference directory")
    args = parser.parse_args()
    fetch(args.repo, args.ref, args.output.resolve())


if __name__ == "__main__":
    main()
