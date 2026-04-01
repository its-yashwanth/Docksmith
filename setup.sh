#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Docksmith setup"
echo "Project root: ${ROOT_DIR}"
echo
echo "This project is designed to build and run on Linux."
echo "Suggested workflow:"
echo "  1. Import a local base rootfs tar with scripts/import_base_image.py"
echo "  2. Build: sudo python -m docksmith.cli build -t myapp:latest sample-app"
echo "  3. Run:   sudo python -m docksmith.cli run myapp:latest"
echo
echo "No Python package installation is required; the project uses the standard library."

