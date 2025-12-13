#!/usr/bin/env python3
"""Entry point for python -m tcv_screenshots."""

import argparse
from pathlib import Path

from .render import run


def main():
    parser = argparse.ArgumentParser(
        prog="tcv_screenshots",
        description="Generate screenshots from CAD examples using three-cad-viewer"
    )
    parser.add_argument(
        "examples_dir",
        type=Path,
        help="Directory containing Python example files with main() functions",
    )
    parser.add_argument(
        "screenshots_dir",
        type=Path,
        help="Directory for output PNG screenshots",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode (for debugging)",
    )
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Pause before each screenshot (for debugging)",
    )
    parser.add_argument(
        "--debug",
        type=Path,
        metavar="MODELS_DIR",
        help="Save JSON model files to this directory (for debugging)",
    )

    args = parser.parse_args()

    run(
        examples_dir=args.examples_dir.resolve(),
        screenshots_dir=args.screenshots_dir.resolve(),
        headless=not args.no_headless,
        pause=args.pause,
        debug_models_dir=args.debug.resolve() if args.debug else None,
    )


if __name__ == "__main__":
    main()
