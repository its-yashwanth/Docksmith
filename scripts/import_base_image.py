from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from docksmith.hashing import sha256_file
from docksmith.image_store import ImageStore
from docksmith.manifest import ImageConfig, ImageManifest, LayerEntry
from docksmith.state import DocksmithState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import a prebuilt root filesystem tar as a Docksmith base image.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--tag", default="latest")
    parser.add_argument("--tar", required=True, dest="tar_path")
    parser.add_argument("--cmd", nargs="*", default=[])
    parser.add_argument("--workdir", default="/")
    parser.add_argument("--env", action="append", default=[])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    state = DocksmithState.load()
    state.ensure()
    image_store = ImageStore(state)

    tar_path = Path(args.tar_path).resolve()
    if not tar_path.exists():
        raise SystemExit(f"tar file not found: {tar_path}")

    digest = sha256_file(tar_path)
    layer_path = state.layer_path(digest)
    if not layer_path.exists():
        shutil.copyfile(tar_path, layer_path)

    manifest = ImageManifest.new(
        name=args.name,
        tag=args.tag,
        config=ImageConfig(Env=list(args.env), Cmd=list(args.cmd), WorkingDir=args.workdir),
        layers=[LayerEntry(digest=digest, size=tar_path.stat().st_size, createdBy="<imported base layer>")],
    )
    image_store.save(manifest)
    print(f"Imported base image {args.name}:{args.tag} as {manifest.digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
