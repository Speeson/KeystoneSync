from __future__ import annotations

import argparse
import json
import posixpath
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


DIMENSIONS = ("addon_build", "addon_release")
VERSION_LINE_RE = re.compile(r"^##\s*Version\s*:")


@dataclass
class Impact:
    reasons: dict[str, list[str]] = field(default_factory=lambda: {key: [] for key in DIMENSIONS})
    known_no_release_paths: list[str] = field(default_factory=list)
    known_no_impact_paths: list[str] = field(default_factory=list)
    unknown_paths: list[str] = field(default_factory=list)
    outside_paths: list[str] = field(default_factory=list)

    @property
    def dimensions(self) -> dict[str, bool]:
        return {key: bool(self.reasons[key]) for key in DIMENSIONS}

    def add(self, dimensions: Iterable[str], path: str) -> None:
        for dimension in dimensions:
            if path not in self.reasons[dimension]:
                self.reasons[dimension].append(path)

    def build_only(self, path: str) -> None:
        self.add(("addon_build",), path)
        if path not in self.known_no_release_paths:
            self.known_no_release_paths.append(path)

    def no_impact(self, path: str) -> None:
        if path not in self.known_no_impact_paths:
            self.known_no_impact_paths.append(path)

    def unknown(self, path: str) -> None:
        if path not in self.unknown_paths:
            self.unknown_paths.append(path)

    def outside(self, path: str) -> None:
        if path not in self.outside_paths:
            self.outside_paths.append(path)

    def as_json(self) -> dict[str, object]:
        return {
            **self.dimensions,
            "reasons": self.reasons,
            "known_no_release_paths": self.known_no_release_paths,
            "known_no_impact_paths": self.known_no_impact_paths,
            "unknown_paths": self.unknown_paths,
            "outside_paths": self.outside_paths,
        }


def normalize_path(raw_path: str, repo_root: Path | None = None) -> tuple[str | None, bool]:
    value = raw_path.strip().strip('"').strip("'").replace("\\", "/")
    if not value:
        return None, False

    path = Path(value)
    if path.is_absolute():
        root = (repo_root or Path.cwd()).resolve()
        try:
            value = path.resolve().relative_to(root).as_posix()
        except ValueError:
            return value, True

    while value.startswith("./"):
        value = value[2:]

    normalized = posixpath.normpath(value)
    if normalized in ("", "."):
        return None, False
    if normalized.startswith("../") or normalized == ".." or normalized.startswith("/"):
        return normalized, True
    return normalized, False


def classify_paths(
    paths: Iterable[str],
    *,
    repo_root: Path | None = None,
    toc_version_only: bool = False,
) -> Impact:
    impact = Impact()
    root = repo_root or Path.cwd()
    for raw_path in paths:
        path, outside = normalize_path(raw_path, root)
        if path is None:
            continue
        if outside:
            impact.outside(path)
            continue
        classify_path(path, impact, repo_root=root, toc_version_only=toc_version_only)
    return impact


def classify_path(path: str, impact: Impact, *, repo_root: Path, toc_version_only: bool) -> None:
    if path == "KeystoneSync.lua":
        impact.add(("addon_build", "addon_release"), path)
        return

    if path == "KeystoneSync.toc":
        if toc_version_only or is_toc_version_only_diff(repo_root):
            impact.no_impact(path)
        else:
            impact.add(("addon_build", "addon_release"), path)
        return

    if is_build_only_path(path):
        impact.build_only(path)
        return

    if is_known_no_impact(path):
        impact.no_impact(path)
        return

    if path.endswith((".lua", ".xml", ".tga", ".blp", ".png")):
        impact.add(("addon_build", "addon_release"), path)
        return

    impact.unknown(path)


def is_toc_version_only_diff(repo_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "diff", "--", "KeystoneSync.toc"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return False
    if result.returncode != 0 or not result.stdout.strip():
        return False

    changed_payload_lines: list[str] = []
    for line in result.stdout.splitlines():
        if line.startswith(("diff --git", "index ", "--- ", "+++ ", "@@")):
            continue
        if line.startswith(("+", "-")):
            changed_payload_lines.append(line[1:])
    return bool(changed_payload_lines) and all(VERSION_LINE_RE.match(line) for line in changed_payload_lines)


def is_build_only_path(path: str) -> bool:
    prefixes = (
        ".github/",
        "scripts/",
        "tests/",
    )
    return any(path.startswith(prefix) for prefix in prefixes)


def is_known_no_impact(path: str) -> bool:
    exact = {
        "AGENTS.md",
        "README.md",
        "CHANGELOG.md",
        ".gitignore",
    }
    prefixes = (
        ".changes/",
        "docs/",
        "dist/",
        "build/",
    )
    return path in exact or any(path.startswith(prefix) for prefix in prefixes)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify KeystoneSync addon build/release impact.")
    parser.add_argument("--files", nargs="*", default=[], help="Changed repository paths to classify.")
    parser.add_argument("--stdin", action="store_true", help="Read newline-separated changed paths from stdin.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow an empty changed-path set.")
    parser.add_argument("--toc-version-only", action="store_true", help="Treat KeystoneSync.toc as a Version-only generated diff.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when unknown or outside paths are present.")
    return parser


def read_stdin_paths() -> list[str]:
    return [line.rstrip("\n") for line in sys.stdin if line.strip()]


def render_text(impact: Impact) -> str:
    lines = ["Deployment impact:"]
    dimensions = impact.dimensions
    for dimension in DIMENSIONS:
        lines.append(f"{dimension.upper()}={str(dimensions[dimension]).lower()}")
        for path in impact.reasons[dimension]:
            lines.append(f"  - {path}")
    if impact.unknown_paths:
        lines.append("UNKNOWN_PATHS:")
        lines.extend(f"  - {path}" for path in impact.unknown_paths)
    if impact.outside_paths:
        lines.append("OUTSIDE_PATHS:")
        lines.extend(f"  - {path}" for path in impact.outside_paths)
    if impact.known_no_release_paths:
        lines.append("KNOWN_NO_RELEASE:")
        lines.extend(f"  - {path}" for path in impact.known_no_release_paths)
    if impact.known_no_impact_paths:
        lines.append("KNOWN_NO_PRODUCT_IMPACT:")
        lines.extend(f"  - {path}" for path in impact.known_no_impact_paths)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = list(args.files)
    if args.stdin:
        paths.extend(read_stdin_paths())
    if not paths and not args.allow_empty:
        parser.error("provide --files, --stdin, or --allow-empty")

    impact = classify_paths(paths, repo_root=Path.cwd(), toc_version_only=args.toc_version_only)
    if args.json:
        print(json.dumps(impact.as_json(), indent=2, sort_keys=True))
    else:
        print(render_text(impact))
    if args.strict and (impact.unknown_paths or impact.outside_paths):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
