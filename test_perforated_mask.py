#!/usr/bin/env python3
"""
Test runner for perforated_mask.py using the default test image.
"""

import os
import subprocess
import sys

DEFAULT_TEST_IMAGE = "/Users/davec/projects/uv/Camera Grid/design/Caution 6X4.png"
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "scripts", "perforated_mask.py")

def main():
    if not os.path.isfile(DEFAULT_TEST_IMAGE):
        print(f"Error: default test image not found: {DEFAULT_TEST_IMAGE}", file=sys.stderr)
        sys.exit(1)

    cmd = [
        sys.executable,
        SCRIPT_PATH,
        DEFAULT_TEST_IMAGE,
        "--mm",
        "--hole-size", "3",
        "--spacing", "6",
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
