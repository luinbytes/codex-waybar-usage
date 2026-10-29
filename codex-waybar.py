#!/usr/bin/env python3
"""Compatibility entry point for the former codex-waybar.py name.

Waybar configs that still exec this filename keep working. The implementation
lives in grok-waybar.py.
"""

import os
import sys
from pathlib import Path


def main():
    here = Path(__file__).resolve().parent
    target = here / "grok-waybar.py"
    if not target.is_file():
        target = Path.home() / ".local/share/grok-waybar-usage/grok-waybar.py"
    if not target.is_file():
        print("grok-waybar-usage: grok-waybar.py not found", file=sys.stderr)
        raise SystemExit(1)
    os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])


if __name__ == "__main__":
    main()
