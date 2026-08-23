from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ALLOWED_COMPONENTS = ("addon",)
ALLOWED_TYPES = ("patch", "minor", "major")
ALLOWED_CATEGORIES = ("added", "changed", "fixed", "removed", "security")
TYPE_RANK = {"patch": 0, "minor": 1, "major": 2}
CATEGORY_TITLES = {
    "added": "Novedades",
    "changed": "Cambios",
    "fixed": "Correcciones",
    "removed": "Eliminado",
    "security": "Seguridad",
}
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
VERSION_LINE_RE = re.compile(r"^(##\s*Version\s*:\s*)(\S+)(\s*)$")
CHANGELOG_VERSION_RE = re.compile(r"^##\s+\[([^]]+)](?:\s+-\s+.*)?$")


@dataclass(frozen=True)
class Changeset:
    path: Path
    components: tuple[str, ...]
    type: str
    category: str
    summary: str
    details: tuple[str, ...]

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class ReleasePlan:
    current_version: str
    bump: str
    next_version: str
    changesets: tuple[Changeset, ...]

    @property
    def tag(self) -> str:
        return f"v{self.next_version}"

    @property
    def release_name(self) -> str:
        return f"KeystoneSync {self.next_version}"

    @property
    def asset(self) -> str:
        return f"KeystoneSync-v{self.next_version}.zip"


class ChangesetError(ValueError):
    pass


def parse_semver(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(value.strip())
    if not match:
        raise ChangesetError(f"Invalid semantic version: {value}")
    return tuple(int(part) for part in match.groups())


def bump_version(version: str, bump: str) -> str:
    if bump not in ALLOWED_TYPES:
        raise ChangesetError(f"Invalid bump: {bump}")
    major, minor, patch = parse_semver(version)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def read_addon_version(toc_path: Path) -> str:
    for line in toc_path.read_text(encoding="utf-8-sig").splitlines():
        match = VERSION_LINE_RE.match(line)
        if match:
            version = match.group(2)
            parse_semver(version)
            return version
    raise ChangesetError("KeystoneSync.toc is missing ## Version")


def update_toc_version(toc_path: Path, version: str) -> None:
    parse_semver(version)
    lines = toc_path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    updated: list[str] = []
    changed = False
    for line in lines:
        stripped = line.rstrip("\r\n")
        newline = line[len(stripped):]
        match = VERSION_LINE_RE.match(stripped)
        if match:
            updated.append(f"{match.group(1)}{version}{match.group(3)}{newline}")
            changed = True
        else:
            updated.append(line)
    if not changed:
        raise ChangesetError("KeystoneSync.toc is missing ## Version")
    toc_path.write_text("".join(updated), encoding="utf-8")


def highest_bump(changesets: Iterable[Changeset]) -> str:
    selected: str | None = None
    for changeset in changesets:
        if selected is None or TYPE_RANK[changeset.type] > TYPE_RANK[selected]:
            selected = changeset.type
    if selected is None:
        raise ChangesetError("No matching addon changesets")
    return selected


def validate_changeset(path: Path, raw: object) -> Changeset:
    if not isinstance(raw, dict):
        raise ChangesetError(f"{path}: changeset must be a JSON object")

    components = raw.get("components")
    if not isinstance(components, list) or not components or not all(isinstance(item, str) and item for item in components):
        raise ChangesetError(f"{path}: components must be a non-empty string array")
    unknown_components = sorted(set(components).difference(ALLOWED_COMPONENTS))
    if unknown_components:
        raise ChangesetError(f"{path}: invalid component(s): {', '.join(unknown_components)}")

    change_type = raw.get("type")
    if change_type not in ALLOWED_TYPES:
        raise ChangesetError(f"{path}: type must be one of {', '.join(ALLOWED_TYPES)}")

    category = raw.get("category")
    if category not in ALLOWED_CATEGORIES:
        raise ChangesetError(f"{path}: category must be one of {', '.join(ALLOWED_CATEGORIES)}")

    summary = raw.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ChangesetError(f"{path}: summary is required")

    details = raw.get("details")
    if not isinstance(details, list) or not all(isinstance(item, str) and item.strip() for item in details):
        raise ChangesetError(f"{path}: details must be a string array")

    return Changeset(
        path=path,
        components=tuple(components),
        type=change_type,
        category=category,
        summary=summary.strip(),
        details=tuple(item.strip() for item in details),
    )


def load_changesets(root: Path, component: str = "addon") -> tuple[Changeset, ...]:
    if component not in ALLOWED_COMPONENTS:
        raise ChangesetError(f"Invalid component: {component}")
    pending = root / ".changes" / "pending"
    if not pending.exists():
        return ()

    changesets: list[Changeset] = []
    for path in sorted(pending.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            loaded = json.load(handle)
        changeset = validate_changeset(path, loaded)
        if component in changeset.components:
            changesets.append(changeset)
    return tuple(changesets)


def plan_release(root: Path, requested_bump: str = "auto") -> ReleasePlan:
    if requested_bump != "auto" and requested_bump not in ALLOWED_TYPES:
        raise ChangesetError(f"Invalid bump: {requested_bump}")
    changesets = load_changesets(root, "addon")
    if not changesets:
        raise ChangesetError("No pending addon changesets")
    current_version = read_addon_version(root / "KeystoneSync.toc")
    bump = highest_bump(changesets) if requested_bump == "auto" else requested_bump
    next_version = bump_version(current_version, bump)
    return ReleasePlan(current_version, bump, next_version, changesets)


def render_notes(plan: ReleasePlan) -> str:
    lines = [f"# KeystoneSync {plan.next_version}", ""]
    by_category: dict[str, list[Changeset]] = {category: [] for category in ALLOWED_CATEGORIES}
    for changeset in plan.changesets:
        by_category[changeset.category].append(changeset)

    for category in ALLOWED_CATEGORIES:
        entries = by_category[category]
        if not entries:
            continue
        lines.extend((f"## {CATEGORY_TITLES[category]}", ""))
        for changeset in entries:
            lines.append(f"- {changeset.summary}")
            for detail in changeset.details:
                lines.append(f"  - {detail}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_historical_notes(changelog: str, version: str) -> str:
    parse_semver(version)
    lines = changelog.splitlines()
    start: int | None = None
    end = len(lines)
    for index, line in enumerate(lines):
        match = CHANGELOG_VERSION_RE.match(line.strip())
        if not match:
            continue
        if start is None and match.group(1) == version:
            start = index + 1
            continue
        if start is not None:
            end = index
            break
    if start is None:
        raise ChangesetError(f"CHANGELOG.md is missing version {version}")
    body = "\n".join(lines[start:end]).strip()
    if not body:
        raise ChangesetError(f"CHANGELOG.md version {version} has no release notes")
    return f"# KeystoneSync {version}\n\n{body}\n"


def plan_payload(plan: ReleasePlan) -> dict[str, object]:
    return {
        "component": "addon",
        "current_version": plan.current_version,
        "bump": plan.bump,
        "next_version": plan.next_version,
        "tag": plan.tag,
        "release_name": plan.release_name,
        "asset": plan.asset,
        "changesets": [changeset.name for changeset in plan.changesets],
        "release_notes": render_notes(plan),
    }


def write_release_files(root: Path, plan: ReleasePlan) -> tuple[Path, Path]:
    update_toc_version(root / "KeystoneSync.toc", plan.next_version)
    releases = root / ".changes" / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    notes_path = releases / f"addon-v{plan.next_version}.md"
    metadata_path = releases / f"addon-v{plan.next_version}.json"

    consumed_dir = releases / f"addon-v{plan.next_version}-changesets"
    consumed_dir.mkdir(parents=True, exist_ok=False)
    for changeset in plan.changesets:
        shutil.move(str(changeset.path), consumed_dir / changeset.path.name)

    metadata = {
        "component": "addon",
        "current_version": plan.current_version,
        "version": plan.next_version,
        "bump": plan.bump,
        "tag": plan.tag,
        "release_name": plan.release_name,
        "asset": plan.asset,
        "changesets": [changeset.name for changeset in plan.changesets],
    }
    notes_path.write_text(render_notes(plan), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return notes_path, metadata_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan and prepare KeystoneSync addon releases.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="Validate pending addon changesets.")

    plan = sub.add_parser("plan", help="Calculate the next release without modifying files.")
    plan.add_argument("--bump", default="auto", choices=("auto", *ALLOWED_TYPES))
    plan.add_argument("--json", action="store_true")
    plan.add_argument("--notes-out", type=Path)

    prepare = sub.add_parser("prepare", help="Consume changesets and update KeystoneSync.toc Version.")
    prepare.add_argument("--bump", default="auto", choices=("auto", *ALLOWED_TYPES))
    prepare.add_argument("--json", action="store_true")

    historical = sub.add_parser("historical-notes", help="Extract release notes for an immutable historical tag.")
    historical.add_argument("--version", required=True)
    historical.add_argument("--changelog", required=True, type=Path)
    historical.add_argument("--output", required=True, type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path.cwd()
    if args.command == "historical-notes":
        notes = render_historical_notes(args.changelog.read_text(encoding="utf-8-sig"), args.version)
        args.output.write_text(notes, encoding="utf-8")
        return 0
    if args.command == "validate":
        load_changesets(root, "addon")
        return 0
    plan = plan_release(root, args.bump)
    if args.command == "prepare":
        write_release_files(root, plan)
    if getattr(args, "notes_out", None):
        args.notes_out.write_text(render_notes(plan), encoding="utf-8")
    if args.json:
        print(json.dumps(plan_payload(plan), indent=2, ensure_ascii=False))
    else:
        print(f"addon {plan.current_version} -> {plan.next_version} ({plan.bump})")
        print(f"tag: {plan.tag}")
        print(f"asset: {plan.asset}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
