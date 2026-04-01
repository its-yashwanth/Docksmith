# Docksmith

Docksmith is a simplified Docker-like image builder and container runtime implemented in Python. This repository is shaped around the requirements in `DOCKSMITH.pdf` and [`DOCKSMITH_extracted.txt`](/c:/Users/yashw/OneDrive/Documents/My_projects/Docksmith/DOCKSMITH_extracted.txt): a single CLI-oriented tool, deterministic layer caching, content-addressed storage, Linux-rooted process isolation, and fully offline build/run operation after base images are imported once.

## Project Layout

```text
docksmith/
|-- docksmith/
|   |-- cli.py
|   |-- build_engine.py
|   |-- parser.py
|   |-- instruction.py
|   |-- layer_builder.py
|   |-- cache_manager.py
|   |-- isolation.py
|   |-- container_runtime.py
|   |-- image_store.py
|   |-- manifest.py
|   |-- hashing.py
|   |-- filesystem.py
|   `-- state.py
|-- scripts/
|   `-- import_base_image.py
|-- sample-app/
|   |-- Docksmithfile
|   |-- app.py
|   `-- requirements.txt
|-- ui/
|   `-- index.html
|-- ui_server.py
|-- setup.sh
`-- README.md
```

## Spec Highlights

- `FROM`, `COPY`, `RUN`, `WORKDIR`, `ENV`, and `CMD` are the only supported Docksmithfile instructions.
- `COPY` and `RUN` produce immutable, content-addressed tar delta layers.
- Cache keys include previous layer digest, full instruction text, current `WORKDIR`, current `ENV`, and `COPY` source digests.
- A cache miss cascades to all later layer-producing steps.
- Builds preserve the original `created` timestamp on full cache-hit rebuilds so the manifest digest stays reproducible.
- `RUN` during build and `docksmith run` both use the same Linux isolation path.

## Requirements

- Linux is required for compliant build/run isolation.
- Root privileges are currently required for `chroot`-based isolation.
- No third-party Python packages are required.

## Base Image Import

Import a base root filesystem tar before building any image:

```bash
python scripts/import_base_image.py --name python-base --tag 3.11 --tar /path/to/python-rootfs.tar
```

## Sample App Demo

Cold build:

```bash
sudo python -m docksmith.cli build -t myapp:latest sample-app
```

Warm build:

```bash
sudo python -m docksmith.cli build -t myapp:latest sample-app
```

Run the container:

```bash
sudo python -m docksmith.cli run myapp:latest
```

Override an environment variable:

```bash
sudo python -m docksmith.cli run -e APP_MESSAGE=Overridden myapp:latest
```

List images:

```bash
python -m docksmith.cli images
```

Remove an image:

```bash
python -m docksmith.cli rmi myapp:latest
```
