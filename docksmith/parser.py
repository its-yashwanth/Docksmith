from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .instruction import (
    CmdInstruction,
    CopyInstruction,
    EnvInstruction,
    FromInstruction,
    Instruction,
    RunInstruction,
    WorkdirInstruction,
)


class ParseError(ValueError):
    pass


def parse_docksmithfile(path: Path) -> List[Instruction]:
    instructions: list[Instruction] = []
    for line_number, original_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw_line = original_line.rstrip("\r\n")
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        keyword, _, remainder = stripped.partition(" ")
        keyword = keyword.upper()
        if not remainder and keyword not in {"CMD"}:
            raise ParseError(f"{path}:{line_number}: missing arguments for {keyword}")

        if keyword == "FROM":
            image_ref = remainder.strip()
            if ":" in image_ref:
                image, tag = image_ref.rsplit(":", 1)
            else:
                image, tag = image_ref, "latest"
            instructions.append(FromInstruction(keyword, raw_line, line_number, image=image, tag=tag))
            continue

        if keyword == "COPY":
            parts = remainder.split()
            if len(parts) != 2:
                raise ParseError(f"{path}:{line_number}: COPY requires exactly 2 arguments")
            instructions.append(CopyInstruction(keyword, raw_line, line_number, src=parts[0], dest=parts[1]))
            continue

        if keyword == "RUN":
            command = remainder.strip()
            if not command:
                raise ParseError(f"{path}:{line_number}: RUN requires a command")
            instructions.append(RunInstruction(keyword, raw_line, line_number, command=command))
            continue

        if keyword == "WORKDIR":
            workdir = remainder.strip()
            if not workdir:
                raise ParseError(f"{path}:{line_number}: WORKDIR requires a path")
            instructions.append(WorkdirInstruction(keyword, raw_line, line_number, path=workdir))
            continue

        if keyword == "ENV":
            key, sep, value = remainder.partition("=")
            if not sep or not key.strip():
                raise ParseError(f"{path}:{line_number}: ENV requires KEY=value")
            instructions.append(
                EnvInstruction(keyword, raw_line, line_number, key=key.strip(), value=value)
            )
            continue

        if keyword == "CMD":
            try:
                parsed = json.loads(remainder)
            except json.JSONDecodeError as exc:
                raise ParseError(f"{path}:{line_number}: invalid CMD JSON: {exc}") from exc
            if not isinstance(parsed, list) or not parsed or any(not isinstance(item, str) for item in parsed):
                raise ParseError(f"{path}:{line_number}: CMD must be a non-empty JSON string array")
            instructions.append(CmdInstruction(keyword, raw_line, line_number, argv=parsed))
            continue

        raise ParseError(f"{path}:{line_number}: unrecognized instruction {keyword}")

    if not instructions:
        raise ParseError(f"{path}: Docksmithfile is empty")
    if not isinstance(instructions[0], FromInstruction):
        raise ParseError(f"{path}:{instructions[0].line_number}: first instruction must be FROM")
    return instructions
