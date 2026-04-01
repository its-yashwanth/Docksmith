from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .filesystem import ensure_container_dir, extract_layers
from .image_store import ImageRef, ImageStore
from .isolation import run_isolated
from .state import DocksmithState


class ContainerRuntime:
    def __init__(self, state: DocksmithState, image_store: ImageStore):
        self.state = state
        self.image_store = image_store

    def run(
        self,
        *,
        image_ref: ImageRef,
        command_override: list[str] | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> int:
        manifest = self.image_store.load(image_ref)
        command = command_override or manifest.config.Cmd
        if not command:
            raise ValueError(f"image {image_ref.display()} has no CMD and no runtime command override was provided")

        env = {}
        for item in manifest.config.Env:
            key, value = item.split("=", 1)
            env[key] = value
        env.update(env_overrides or {})
        env.setdefault("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")

        temp_dir = Path(tempfile.mkdtemp(prefix="docksmith-run-"))
        try:
            layer_paths = [self.state.layer_path(layer.digest) for layer in manifest.layers]
            for layer_path in layer_paths:
                if not layer_path.exists():
                    raise FileNotFoundError(
                        f"missing layer file for image {image_ref.display()}: {layer_path.name}"
                    )
            extract_layers(layer_paths, temp_dir)
            ensure_container_dir(temp_dir, manifest.config.WorkingDir or "/")
            result = run_isolated(
                rootfs=temp_dir,
                argv=command,
                env=env,
                workdir=manifest.config.WorkingDir or "/",
            )
            print(f"Container exited with code {result.exit_code}")
            return result.exit_code
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
