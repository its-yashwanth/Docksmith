from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instruction:
    keyword: str
    raw: str
    line_number: int


@dataclass(frozen=True)
class FromInstruction(Instruction):
    image: str
    tag: str


@dataclass(frozen=True)
class CopyInstruction(Instruction):
    src: str
    dest: str


@dataclass(frozen=True)
class RunInstruction(Instruction):
    command: str


@dataclass(frozen=True)
class WorkdirInstruction(Instruction):
    path: str


@dataclass(frozen=True)
class EnvInstruction(Instruction):
    key: str
    value: str


@dataclass(frozen=True)
class CmdInstruction(Instruction):
    argv: list[str]

