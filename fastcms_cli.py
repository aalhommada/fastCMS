#!/usr/bin/env python3
"""
FastCMS Command Line Interface — backward-compatible shim.

The actual CLI lives in cli/entry.py. This file exists so that
`python fastcms_cli.py` continues to work for users who run it directly.
"""

import sys
from pathlib import Path

# Add repo root to path for source-mode usage
sys.path.insert(0, str(Path(__file__).parent))

from cli.entry import cli  # noqa: E402

if __name__ == "__main__":
    cli()
