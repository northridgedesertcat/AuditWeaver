"""Compatibility entry point; all lifecycle logic lives in dev.py."""

import sys

from dev import main


if __name__ == "__main__":
    raise SystemExit(main(["start", *sys.argv[1:]]))
