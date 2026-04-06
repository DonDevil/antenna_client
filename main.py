"""Repository entry point for the antenna client."""

from pathlib import Path
import sys


def main() -> None:
    project_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(project_root / "src"))
    sys.path.insert(0, str(project_root))

    from src.main import main as app_main

    app_main()


if __name__ == "__main__":
    main()