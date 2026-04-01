from __future__ import annotations

import io
import tarfile
from pathlib import Path

from .filesystem import FileSnapshot
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

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for relative in changed_paths:
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
