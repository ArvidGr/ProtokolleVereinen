"""Einstiegspunkt für PyInstaller bzw. direkten Start: `python run_protokoll.py run`."""
import sys

from protokoll.main import main

if __name__ == "__main__":
    sys.exit(main())
