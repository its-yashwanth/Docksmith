from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .hashing import canonical_json_bytes, canonical_json_digest


@dataclass
class ImageConfig:
    Env: list[str] = field(default_factory=list)
    Cmd: list[str] = field(default_factory=list)
    WorkingDir: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "Env": list(self.Env),
            "Cmd": list(self.Cmd),
            "WorkingDir": self.WorkingDir,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ImageConfig":
        return cls(
            Env=list(payload.get("Env", [])),
            Cmd=list(payload.get("Cmd", [])),
            WorkingDir=payload.get("WorkingDir", ""),
        )


@dataclass
class LayerEntry:
    digest: str
    size: int
    createdBy: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "size": self.size,
            "createdBy": self.createdBy,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LayerEntry":
        return cls(
            digest=payload["digest"],
            size=int(payload["size"]),
            createdBy=payload["createdBy"],
        )


@dataclass
class ImageManifest:
    name: str
    tag: str
    digest: str
    created: str
    config: ImageConfig
    layers: list[LayerEntry]

    def digestless_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tag": self.tag,
            "digest": "",
            "created": self.created,
            "config": self.config.to_dict(),
            "layers": [layer.to_dict() for layer in self.layers],
        }

    def finalize_digest(self) -> str:
        self.digest = canonical_json_digest(self.digestless_payload())
        return self.digest

    def to_dict(self) -> dict[str, Any]:
        payload = self.digestless_payload()
        payload["digest"] = self.digest
        return payload

    def save(self, path: Path) -> None:
        self.finalize_digest()
        path.write_bytes(canonical_json_bytes(self.to_dict()))

    @classmethod
    def load(cls, path: Path) -> "ImageManifest":
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ImageManifest":
        return cls(
            name=payload["name"],
            tag=payload["tag"],
            digest=payload["digest"],
            created=payload["created"],
            config=ImageConfig.from_dict(payload.get("config", {})),
            layers=[LayerEntry.from_dict(item) for item in payload.get("layers", [])],
        )

    @classmethod
    def new(
        cls,
        *,
        name: str,
        tag: str,
        config: ImageConfig,
        layers: list[LayerEntry],
        created: str | None = None,
    ) -> "ImageManifest":
        return cls(
            name=name,
            tag=tag,
            digest="",
            created=created or deterministic_created_timestamp(
                {
                    "name": name,
                    "tag": tag,
                    "config": config.to_dict(),
                    "layers": [layer.to_dict() for layer in layers],
                }
            ),
            config=config,
            layers=layers,
        )


def deterministic_created_timestamp(payload: dict[str, Any]) -> str:
    digest = canonical_json_digest(payload).split(":", 1)[1]
    epoch = datetime(2020, 1, 1, tzinfo=timezone.utc)
    # Keep timestamps stable for identical inputs while still looking like real ISO-8601 times.
    offset_seconds = int(digest[:12], 16) % (30 * 365 * 24 * 60 * 60)
    return (epoch + timedelta(seconds=offset_seconds)).isoformat()
