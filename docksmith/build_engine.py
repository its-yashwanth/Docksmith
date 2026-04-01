from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .cache_manager import CacheManager, CacheRecord
from .filesystem import (
    copy_into_rootfs,
    ensure_container_dir,
    extract_layers,
    resolve_copy_sources,
    snapshot_filesystem,
)
from .hashing import canonical_json_digest, sha256_file
from .image_store import ImageRef, ImageStore
from .instruction import (
    CmdInstruction,
    CopyInstruction,
    EnvInstruction,
    FromInstruction,
    Instruction,
    RunInstruction,
    WorkdirInstruction,
)
from .isolation import run_isolated
from .layer_builder import build_layer_from_diff
from .manifest import ImageConfig, ImageManifest, LayerEntry
from .parser import parse_docksmithfile
from .state import DocksmithState


@dataclass
class BuildResult:
    manifest: ImageManifest
    duration_seconds: float


class BuildEngine:
    def __init__(self, state: DocksmithState, image_store: ImageStore, cache_manager: CacheManager):
        self.state = state
        self.image_store = image_store
        self.cache_manager = cache_manager

    def build(self, *, context_dir: Path, image_ref: ImageRef, no_cache: bool = False) -> BuildResult:
        context_dir = context_dir.resolve()
        docksmithfile_path = context_dir / "Docksmithfile"
        instructions = parse_docksmithfile(docksmithfile_path)

        started_at = time.perf_counter()
        temp_root = Path(tempfile.mkdtemp(prefix="docksmith-build-"))
        produced_layers: list[LayerEntry] = []
        layer_step_seen = False
        all_layer_steps_hit = not no_cache
        cascade_miss = no_cache

        try:
            first = instructions[0]
            assert isinstance(first, FromInstruction)
            base_ref = ImageRef(name=first.image, tag=first.tag)
            try:
                base_manifest = self.image_store.load(base_ref)
            except FileNotFoundError as exc:
                raise ValueError(
                    f"Docksmithfile:{first.line_number}: base image not found: {base_ref.display()}"
                ) from exc
            base_layers = list(base_manifest.layers)
            extract_layers([self.state.layer_path(layer.digest) for layer in base_layers], temp_root)

            env = self._env_dict_from_config(base_manifest.config)
            current_workdir = self._normalize_workdir(base_manifest.config.WorkingDir or "/")
            current_cmd = list(base_manifest.config.Cmd)
            previous_layer_digest = base_manifest.digest

            total_steps = len(instructions)
            print(f"Step 1/{total_steps} : {first.raw}")

            for index, instruction in enumerate(instructions[1:], start=2):
                if isinstance(instruction, WorkdirInstruction):
                    current_workdir = self._normalize_workdir(instruction.path)
                    print(f"Step {index}/{total_steps} : {instruction.raw}")
                    continue

                if isinstance(instruction, EnvInstruction):
                    env[instruction.key] = instruction.value
                    print(f"Step {index}/{total_steps} : {instruction.raw}")
                    continue

                if isinstance(instruction, CmdInstruction):
                    current_cmd = list(instruction.argv)
                    print(f"Step {index}/{total_steps} : {instruction.raw}")
                    continue

                if not isinstance(instruction, (CopyInstruction, RunInstruction)):
                    raise RuntimeError(f"unsupported instruction type: {instruction}")

                layer_step_seen = True
                ensure_container_dir(temp_root, current_workdir or "/")
                step_start = time.perf_counter()
                cache_key = self._cache_key(
                    instruction=instruction,
                    context_dir=context_dir,
                    previous_layer_digest=previous_layer_digest,
                    current_workdir=current_workdir,
                    env=env,
                )
                cache_record = None if no_cache or cascade_miss else self.cache_manager.get(cache_key)
                if cache_record and self.state.layer_path(cache_record.layer_digest).exists():
                    layer_path = self.state.layer_path(cache_record.layer_digest)
                    extract_layers([layer_path], temp_root)
                    duration = time.perf_counter() - step_start
                    layer_entry = LayerEntry(
                        digest=cache_record.layer_digest,
                        size=layer_path.stat().st_size,
                        createdBy=instruction.raw,
                    )
                    produced_layers.append(layer_entry)
                    previous_layer_digest = layer_entry.digest
                    print(f"Step {index}/{total_steps} : {instruction.raw} [CACHE HIT] {duration:.2f}s")
                    continue

                all_layer_steps_hit = False
                cascade_miss = True
                before = snapshot_filesystem(temp_root)
                if isinstance(instruction, CopyInstruction):
                    sources = resolve_copy_sources(context_dir, instruction.src)
                    copy_into_rootfs(context_dir, sources, instruction.src, instruction.dest, temp_root)
                else:
                    run_env = dict(env)
                    run_env.setdefault("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
                    result = run_isolated(
                        rootfs=temp_root,
                        argv=["/bin/sh", "-lc", instruction.command],
                        env=run_env,
                        workdir=current_workdir or "/",
                    )
                    if result.exit_code != 0:
                        raise RuntimeError(
                            f"RUN failed at line {instruction.line_number} with exit code {result.exit_code}"
                        )
                after = snapshot_filesystem(temp_root)
                layer_entry = build_layer_from_diff(
                    state=self.state,
                    rootfs=temp_root,
                    before=before,
                    after=after,
                    created_by=instruction.raw,
                )
                produced_layers.append(layer_entry)
                previous_layer_digest = layer_entry.digest
                if not no_cache:
                    self.cache_manager.put(CacheRecord(cache_key=cache_key, layer_digest=layer_entry.digest))
                duration = time.perf_counter() - step_start
                print(f"Step {index}/{total_steps} : {instruction.raw} [CACHE MISS] {duration:.2f}s")

            existing_manifest = self.image_store.load(image_ref) if self.image_store.exists(image_ref) else None
            created = existing_manifest.created if existing_manifest is not None and all_layer_steps_hit else None
            if not layer_step_seen:
                all_layer_steps_hit = existing_manifest is not None
                if all_layer_steps_hit:
                    created = existing_manifest.created

            final_manifest = ImageManifest.new(
                name=image_ref.name,
                tag=image_ref.tag,
                created=created,
                config=ImageConfig(
                    Env=[f"{key}={env[key]}" for key in sorted(env)],
                    Cmd=current_cmd,
                    WorkingDir=current_workdir,
                ),
                layers=[*base_layers, *produced_layers],
            )
            self.image_store.save(final_manifest)
            duration = time.perf_counter() - started_at
            print(f"Successfully built {final_manifest.digest} {image_ref.display()} ({duration:.2f}s)")
            return BuildResult(manifest=final_manifest, duration_seconds=duration)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def _cache_key(
        self,
        *,
        instruction: Instruction,
        context_dir: Path,
        previous_layer_digest: str,
        current_workdir: str,
        env: dict[str, str],
    ) -> str:
        env_state = "\n".join(f"{key}={env[key]}" for key in sorted(env))
        payload: dict[str, object] = {
            "previous_layer_digest": previous_layer_digest,
            "instruction": instruction.raw,
            "workdir": current_workdir or "",
            "env_state": env_state,
        }
        if isinstance(instruction, CopyInstruction):
            sources = resolve_copy_sources(context_dir, instruction.src)
            payload["copy_source_hashes"] = "".join(sha256_file(source) for source in sources)
        return canonical_json_digest(payload)

    @staticmethod
    def _env_dict_from_config(config: ImageConfig) -> dict[str, str]:
        env: dict[str, str] = {}
        for item in config.Env:
            key, value = item.split("=", 1)
            env[key] = value
        return env

    @staticmethod
    def _normalize_workdir(path: str) -> str:
        if not path:
            return "/"
        if path.startswith("/"):
            return path
        return f"/{path}"
