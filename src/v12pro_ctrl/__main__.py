"""Erlaubt `python -m v12pro_ctrl` als Alternative zum installierten
`v12pro-ctrl`-Kommando."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
