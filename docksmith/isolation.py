from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class IsolationError(RuntimeError):
    pass


@dataclass(frozen=True)
class IsolationResult:
    exit_code: int


def ensure_linux() -> None:
    if os.name != "posix" or platform.system() != "Linux":
        raise IsolationError(
            "Docksmith runtime/build isolation requires Linux. Run this project inside a Linux VM or WSL2."
        )


def ensure_privileged() -> None:
    if os.geteuid() != 0:
        raise IsolationError(
            "Docksmith isolation currently requires root privileges to use chroot safely. Re-run with sudo inside Linux."
        )


def run_isolated(
    *,
    rootfs: Path,
    argv: list[str],
    env: dict[str, str],
    workdir: str,
) -> IsolationResult:
    ensure_linux()
    ensure_privileged()

    helper = Path(__file__).resolve().with_name("_isolation_helper.py")
    command = [
        sys.executable,
        str(helper),
        str(rootfs),
        workdir,
        *argv,
    ]
    completed = subprocess.run(command, env=env, check=False)
    return IsolationResult(exit_code=completed.returncode)

