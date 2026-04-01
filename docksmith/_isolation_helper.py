from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 4:
        raise SystemExit("usage: _isolation_helper.py <rootfs> <workdir> <argv...>")

    rootfs = Path(sys.argv[1]).resolve()
    workdir = sys.argv[2] or "/"
    argv = sys.argv[3:]

    os.chdir(rootfs)
    if hasattr(os, "unshare"):
        flags = 0
        for flag_name in ("CLONE_NEWNS", "CLONE_NEWUTS", "CLONE_NEWIPC", "CLONE_NEWNET"):
            flags |= getattr(os, flag_name, 0)
        if flags:
            os.unshare(flags)
    os.chroot(".")
    os.chdir(workdir if workdir else "/")
    os.execvpe(argv[0], argv, os.environ)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
