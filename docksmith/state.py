from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


def _default_home() -> Path:
    override = os.environ.get("DOCKSMITH_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home().joinpath(".docksmith")


@dataclass(frozen=True)
class DocksmithState:
    root: Path
    images_dir: Path
    layers_dir: Path
    cache_dir: Path

    @classmethod
    def load(cls) -> "DocksmithState":
        root = _default_home()
        return cls(
            root=root,
            images_dir=root / "images",
            layers_dir=root / "layers",
            cache_dir=root / "cache",
        )

    def ensure(self) -> None:
        try:
            self.images_dir.mkdir(parents=True, exist_ok=True)
            self.layers_dir.mkdir(parents=True, exist_ok=True)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OSError(
                f"unable to initialize Docksmith state directory at {self.root}. "
                "Set DOCKSMITH_HOME to a writable path if needed."
            ) from exc

    def image_manifest_path(self, name: str, tag: str) -> Path:
        safe_name = quote(name, safe="")
        safe_tag = quote(tag, safe="")
        return self.images_dir / f"{safe_name}__{safe_tag}.json"

    def layer_path(self, digest: str) -> Path:
        return self.layers_dir / f"{digest.replace(':', '_')}.tar"

    def cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key.replace(':', '_')}.json"
