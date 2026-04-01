from __future__ import annotations

import glob
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


def container_path_to_host(rootfs: Path, container_path: str) -> Path:
    if not container_path.startswith("/"):
        raise ValueError(f"container path must be absolute: {container_path}")
    relative = PurePosixPath(container_path).relative_to("/")
    return rootfs.joinpath(*relative.parts)


def ensure_container_dir(rootfs: Path, container_path: str) -> Path:
    path = container_path_to_host(rootfs, container_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def extract_layer(layer_tar: Path, rootfs: Path) -> None:
    with tarfile.open(layer_tar, "r") as archive:
        root_resolved = rootfs.resolve()
        for member in archive.getmembers():
            target = (rootfs / member.name).resolve()
            if target != root_resolved and root_resolved not in target.parents:
                raise ValueError(f"layer attempted to escape rootfs: {member.name}")
        archive.extractall(rootfs)


def extract_layers(layer_paths: list[Path], rootfs: Path) -> None:
    for layer_path in layer_paths:
        extract_layer(layer_path, rootfs)


@dataclass(frozen=True)
class FileSnapshot:
    relative_path: str
    is_dir: bool
    size: int
    mode: int
    digest: str | None


def snapshot_filesystem(rootfs: Path) -> dict[str, FileSnapshot]:
    import hashlib

    snapshots: dict[str, FileSnapshot] = {}
    for current_path in sorted(rootfs.rglob("*")):
        relative = current_path.relative_to(rootfs).as_posix()
        stat = current_path.lstat()
        if current_path.is_dir():
            snapshots[relative] = FileSnapshot(relative, True, 0, stat.st_mode & 0o777, None)
            continue
        if not current_path.is_file():
            continue
        digest = hashlib.sha256(current_path.read_bytes()).hexdigest()
        snapshots[relative] = FileSnapshot(
            relative_path=relative,
            is_dir=False,
            size=stat.st_size,
            mode=stat.st_mode & 0o777,
            digest=digest,
        )
    return snapshots


def resolve_copy_sources(context_dir: Path, pattern: str) -> list[Path]:
    matches = glob.glob(str(context_dir / pattern), recursive=True)
    if not matches:
        raise FileNotFoundError(f"COPY source did not match any files: {pattern}")

    resolved: list[Path] = []
    for match in sorted(matches):
        match_path = Path(match)
        if match_path.is_dir():
            for child in sorted(match_path.rglob("*")):
                if child.is_file():
                    resolved.append(child.resolve())
        elif match_path.is_file():
            resolved.append(match_path.resolve())

    context_root = context_dir.resolve()
    unique = {path for path in resolved}
    if not unique:
        raise FileNotFoundError(f"COPY source did not resolve to files: {pattern}")

    for file_path in unique:
        if context_root != file_path and context_root not in file_path.parents:
            raise ValueError(f"COPY source escapes build context: {file_path}")

    return sorted(unique, key=lambda item: item.relative_to(context_root).as_posix())


def copy_into_rootfs(context_dir: Path, sources: list[Path], src_pattern: str, dest: str, rootfs: Path) -> None:
    destination = dest if dest.startswith("/") else f"/{dest}"
    destination_root = container_path_to_host(rootfs, destination)
    context_root = context_dir.resolve()
    source_has_glob = any(char in src_pattern for char in "*?[")

    if len(sources) == 1 and not source_has_glob and not dest.endswith("/"):
        destination_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sources[0], destination_root)
        return

    destination_root.mkdir(parents=True, exist_ok=True)

    for source in sources:
        relative = source.relative_to(context_root)
        target = destination_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
