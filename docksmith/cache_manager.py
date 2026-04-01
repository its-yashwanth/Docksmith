from __future__ import annotations

import json
from dataclasses import dataclass

from .state import DocksmithState


@dataclass(frozen=True)
class CacheRecord:
    cache_key: str
    layer_digest: str

    def to_dict(self) -> dict[str, str]:
        return {
            "cache_key": self.cache_key,
            "layer_digest": self.layer_digest,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> "CacheRecord":
        return cls(cache_key=payload["cache_key"], layer_digest=payload["layer_digest"])


class CacheManager:
    def __init__(self, state: DocksmithState):
        self.state = state
        self.state.ensure()

    def get(self, cache_key: str) -> CacheRecord | None:
        path = self.state.cache_path(cache_key)
        if not path.exists():
            return None
        return CacheRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def put(self, record: CacheRecord) -> None:
        path = self.state.cache_path(record.cache_key)
        path.write_text(json.dumps(record.to_dict(), sort_keys=True), encoding="utf-8")
