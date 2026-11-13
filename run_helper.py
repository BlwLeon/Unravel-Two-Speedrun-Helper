"""Entry point for PyInstaller and for running from source: python run_helper.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ut2helper.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
