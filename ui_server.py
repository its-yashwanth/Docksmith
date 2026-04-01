from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> int:
    ui_dir = Path(__file__).resolve().parent / "ui"
    handler = partial(SimpleHTTPRequestHandler, directory=str(ui_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 8000), handler)
    print("Serving Docksmith UI at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

