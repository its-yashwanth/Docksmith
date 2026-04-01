import os
from pathlib import Path


def main() -> None:
    message = os.environ.get("APP_MESSAGE", "missing message")
    marker = Path("/app/runtime-output.txt")
    marker.write_text(f"{message}\n", encoding="utf-8")
    print("Docksmith sample app")
    print(f"APP_MESSAGE={message}")
    print(f"Wrote marker file inside container: {marker}")


if __name__ == "__main__":
    main()
