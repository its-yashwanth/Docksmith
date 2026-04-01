from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build_engine import BuildEngine
from .cache_manager import CacheManager
from .container_runtime import ContainerRuntime
from .image_store import ImageRef, ImageStore
from .isolation import IsolationError
from .parser import ParseError
from .state import DocksmithState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docksmith")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("-t", "--tag", required=True, dest="image")
    build_parser.add_argument("--no-cache", action="store_true")
    build_parser.add_argument("context")

    subparsers.add_parser("images")

    rmi_parser = subparsers.add_parser("rmi")
    rmi_parser.add_argument("image")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("-e", "--env", action="append", default=[])
    run_parser.add_argument("image")
    run_parser.add_argument("cmd", nargs=argparse.REMAINDER)

    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        state = DocksmithState.load()
        image_store = ImageStore(state)
        cache_manager = CacheManager(state)

        if args.command == "build":
            engine = BuildEngine(state, image_store, cache_manager)
            engine.build(
                context_dir=Path(args.context),
                image_ref=ImageRef.parse(args.image),
                no_cache=args.no_cache,
            )
            return 0

        if args.command == "images":
            manifests = image_store.list_images()
            print(f"{'NAME':20} {'TAG':12} {'ID':12} CREATED")
            for manifest in manifests:
                image_id = manifest.digest.split(":", 1)[1][:12]
                print(f"{manifest.name:20} {manifest.tag:12} {image_id:12} {manifest.created}")
            return 0

        if args.command == "rmi":
            ref = ImageRef.parse(args.image)
            image_store.delete(ref)
            print(f"Removed {ref.display()}")
            return 0

        if args.command == "run":
            ref = ImageRef.parse(args.image)
            env_overrides: dict[str, str] = {}
            for item in args.env:
                key, sep, value = item.partition("=")
                if not sep:
                    raise ValueError(f"invalid -e value, expected KEY=value: {item}")
                env_overrides[key] = value
            runtime = ContainerRuntime(state, image_store)
            command_override = args.cmd if args.cmd else None
            return runtime.run(image_ref=ref, command_override=command_override, env_overrides=env_overrides)

        raise SystemExit(f"unknown command: {args.command}")
    except (OSError, FileNotFoundError, ValueError, RuntimeError, ParseError, IsolationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
