from __future__ import annotations

import io
import tarfile
from pathlib import Path, PurePosixPath

from .filesystem import FileSnapshot, WHITEOUT_PREFIX
from .hashing import sha256_bytes
from .manifest import LayerEntry
from .state import DocksmithState


def _normalize_tar_info(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    return info


def build_layer_from_diff(
    *,
    state: DocksmithState,
    rootfs: Path,
    before: dict[str, FileSnapshot],
    after: dict[str, FileSnapshot],
    created_by: str,
) -> LayerEntry:
    changed_paths = sorted(
        path
        for path, snapshot in after.items()
        if path not in before or before[path] != snapshot
    )
    deleted_paths = _top_level_deleted_paths(before=before, after=after)

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for entry_type, relative in sorted(
            [("change", path) for path in changed_paths] + [("delete", path) for path in deleted_paths],
            key=lambda item: item[1],
        ):
            if entry_type == "delete":
                _add_whiteout(archive, relative)
                continue
            current_path = rootfs / relative
            snapshot = after[relative]
            info = archive.gettarinfo(str(current_path), arcname=relative)
            if snapshot.is_dir:
                archive.addfile(_normalize_tar_info(info))
                continue
            with current_path.open("rb") as handle:
                archive.addfile(_normalize_tar_info(info), handle)

    raw_bytes = buffer.getvalue()
    digest = sha256_bytes(raw_bytes)
    layer_path = state.layer_path(digest)
    if not layer_path.exists():
        layer_path.write_bytes(raw_bytes)

    return LayerEntry(digest=digest, size=len(raw_bytes), createdBy=created_by)


def _top_level_deleted_paths(
    *,
    before: dict[str, FileSnapshot],
    after: dict[str, FileSnapshot],
) -> list[str]:
    deleted = sorted(path for path in before if path not in after)
    top_level: list[str] = []
    for path in deleted:
        parts = path.split("/")
        if any("/".join(parts[:index]) in before and "/".join(parts[:index]) not in after for index in range(1, len(parts))):
            continue
        top_level.append(path)
    return top_level


def _add_whiteout(archive: tarfile.TarFile, relative: str) -> None:
    relative_path = PurePosixPath(relative)
    if str(relative_path.parent) == ".":
        whiteout_name = f"{WHITEOUT_PREFIX}{relative_path.name}"
    else:
        whiteout_name = str(relative_path.parent / f"{WHITEOUT_PREFIX}{relative_path.name}")
    info = tarfile.TarInfo(name=whiteout_name)
    info.size = 0
    info.mode = 0o644
    archive.addfile(_normalize_tar_info(info), io.BytesIO(b""))
