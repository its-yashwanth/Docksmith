from __future__ import annotations

from dataclasses import dataclass

from .manifest import ImageManifest
from .state import DocksmithState


@dataclass(frozen=True)
class ImageRef:
    name: str
    tag: str

    @classmethod
    def parse(cls, value: str) -> "ImageRef":
        if ":" in value:
            name, tag = value.rsplit(":", 1)
        else:
            name, tag = value, "latest"
        if not name or not tag:
            raise ValueError(f"invalid image reference: {value}")
        return cls(name=name, tag=tag)

    def display(self) -> str:
        return f"{self.name}:{self.tag}"


class ImageStore:
    def __init__(self, state: DocksmithState):
        self.state = state
        self.state.ensure()

    def exists(self, ref: ImageRef) -> bool:
        return self.state.image_manifest_path(ref.name, ref.tag).exists()

    def load(self, ref: ImageRef) -> ImageManifest:
        path = self.state.image_manifest_path(ref.name, ref.tag)
        if not path.exists():
            raise FileNotFoundError(f"image not found: {ref.display()}")
        return ImageManifest.load(path)

    def save(self, manifest: ImageManifest) -> None:
        path = self.state.image_manifest_path(manifest.name, manifest.tag)
        manifest.save(path)

    def delete(self, ref: ImageRef) -> ImageManifest:
        path = self.state.image_manifest_path(ref.name, ref.tag)
        manifest = self.load(ref)
        path.unlink()
        for layer in manifest.layers:
            layer_path = self.state.layer_path(layer.digest)
            if layer_path.exists():
                layer_path.unlink()
        return manifest

    def list_images(self) -> list[ImageManifest]:
        manifests: list[ImageManifest] = []
        for path in sorted(self.state.images_dir.glob("*.json")):
            manifests.append(ImageManifest.load(path))
        return manifests

