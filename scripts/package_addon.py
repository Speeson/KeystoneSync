from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path


SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

ICON_FILE = "icon.tga"


class PackageError(ValueError):
    pass


@dataclass(frozen=True)
class TocInfo:
    version: str
    metadata: dict[str, str]
    files: tuple[Path, ...]


def read_toc(root: Path) -> TocInfo:
    toc = root / "KeystoneSync.toc"
    if not toc.is_file():
        raise PackageError("Missing KeystoneSync.toc")

    metadata: dict[str, str] = {}
    files: list[Path] = [Path("KeystoneSync.toc")]
    for raw in toc.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("##"):
            key, _, value = line[2:].partition(":")
            metadata[key.strip()] = value.strip()
            continue
        if line.startswith("#"):
            continue
        rel = Path(*line.replace("\\", "/").split("/"))
        if rel.is_absolute() or ".." in rel.parts or (rel.parts and re.fullmatch(r"[A-Za-z]:", rel.parts[0])):
            raise PackageError(f"Invalid .toc file entry: {line}")
        if rel not in files:
            files.append(rel)

    version = metadata.get("Version", "")
    if not SEMVER_RE.fullmatch(version):
        raise PackageError("KeystoneSync.toc Version must use MAJOR.MINOR.PATCH")
    if not files:
        raise PackageError("KeystoneSync.toc does not list addon runtime files")
    for rel in files:
        if not (root / rel).is_file():
            raise PackageError(f"Missing .toc file entry: {rel.as_posix()}")
    return TocInfo(version=version, metadata=metadata, files=tuple(files))


def validate_toc(root: Path, *, expected_version: str | None = None) -> TocInfo:
    info = read_toc(root)
    for key in ("Interface", "Title", "Version", "SavedVariables"):
        if not info.metadata.get(key):
            raise PackageError(f"Missing .toc metadata: {key}")
    if not info.metadata["Interface"].isdigit():
        raise PackageError("Interface metadata must be numeric")
    if "KeystoneSyncDB" not in [value.strip() for value in info.metadata["SavedVariables"].split(",")]:
        raise PackageError("SavedVariables metadata must include KeystoneSyncDB")
    if expected_version and info.version != expected_version:
        raise PackageError(f"TOC Version {info.version} does not match expected {expected_version}")
    return info


def package_addon(root: Path, output_dir: Path, *, version: str | None = None) -> Path:
    info = validate_toc(root, expected_version=version)
    output_dir.mkdir(parents=True, exist_ok=True)
    staging = output_dir / "KeystoneSync"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    for rel in info.files:
        target = staging / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, target)

    icon = root / ICON_FILE
    has_icon = icon.is_file()
    if has_icon:
        shutil.copy2(icon, staging / ICON_FILE)

    asset_name = f"KeystoneSync-v{info.version}.zip"
    zip_path = output_dir / asset_name
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output_dir).as_posix())

    validate_zip(zip_path, info.files, info.version, has_icon=has_icon)
    return zip_path


def validate_zip(zip_path: Path, expected_files: tuple[Path, ...], expected_version: str, *, has_icon: bool = False) -> None:
    if not zip_path.is_file():
        raise PackageError(f"Missing ZIP: {zip_path}")
    expected_asset = f"KeystoneSync-v{expected_version}.zip"
    if zip_path.name != expected_asset:
        raise PackageError(f"ZIP filename must be {expected_asset}")
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if not names:
            raise PackageError("ZIP is empty")
        if any(not name.startswith("KeystoneSync/") for name in names):
            raise PackageError("ZIP entries must stay under KeystoneSync/")
        expected_names = {f"KeystoneSync/{rel.as_posix()}" for rel in expected_files}
        if has_icon:
            expected_names.add(f"KeystoneSync/{ICON_FILE}")
        missing = sorted(expected_names.difference(names))
        if missing:
            raise PackageError(f"ZIP missing expected files: {', '.join(missing)}")
        unexpected = sorted(set(names).difference(expected_names))
        if unexpected:
            raise PackageError(f"ZIP contains unexpected files: {', '.join(unexpected)}")
        toc_text = archive.read("KeystoneSync/KeystoneSync.toc").decode("utf-8-sig")
    if f"## Version: {expected_version}" not in toc_text:
        raise PackageError("ZIP TOC Version does not match expected version")


def validate_zip_against_source(zip_path: Path, root: Path, expected_version: str) -> None:
    info = validate_toc(root, expected_version=expected_version)
    icon = root / ICON_FILE
    has_icon = icon.is_file()
    validate_zip(zip_path, info.files, expected_version, has_icon=has_icon)
    with zipfile.ZipFile(zip_path) as archive:
        for rel in info.files:
            name = f"KeystoneSync/{rel.as_posix()}"
            if archive.read(name) != (root / rel).read_bytes():
                raise PackageError(f"ZIP runtime file differs from source: {rel.as_posix()}")
        if has_icon:
            name = f"KeystoneSync/{ICON_FILE}"
            if archive.read(name) != icon.read_bytes():
                raise PackageError(f"ZIP runtime file differs from source: {ICON_FILE}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and package KeystoneSync addon.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--version")
    validate.add_argument("--source-root", default=Path.cwd(), type=Path)
    package = sub.add_parser("package")
    package.add_argument("--version")
    package.add_argument("--source-root", default=Path.cwd(), type=Path)
    package.add_argument("--output-dir", default="dist", type=Path)
    package.add_argument("--print-path", action="store_true")
    verify = sub.add_parser("verify-package")
    verify.add_argument("--version", required=True)
    verify.add_argument("--source-root", default=Path.cwd(), type=Path)
    verify.add_argument("--zip", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.source_root.resolve()
    if args.command == "validate":
        validate_toc(root, expected_version=args.version)
        return 0
    if args.command == "verify-package":
        validate_zip_against_source(args.zip, root, args.version)
        return 0
    zip_path = package_addon(root, args.output_dir, version=args.version)
    if args.print_path:
        print(zip_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
