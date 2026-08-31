#!/usr/bin/env python3
"""Run EarA from the source tree: ./eara gui"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eara.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
