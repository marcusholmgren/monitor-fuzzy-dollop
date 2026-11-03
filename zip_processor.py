#!/usr/bin/env python3
"""Executable entrypoint for the Standalone Zip File Processor Service."""

import sys
from pathlib import Path

# Allow importing src when invoked directly from root or elsewhere
sys.path.insert(0, str(Path(__file__).parent))

from src.zip_processor import main

if __name__ == "__main__":
    sys.exit(main())
