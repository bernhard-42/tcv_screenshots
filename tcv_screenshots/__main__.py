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
        "models_dir",
        type=Path,
        help="Directory for JSON model files",
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
        "--skip-export",
        action="store_true",
        help="Skip JSON export, only render existing models",
    )
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Skip rendering, only export JSON models",
    )
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Pause before each screenshot (for debugging)",
    )

    args = parser.parse_args()

    run(
        examples_dir=args.examples_dir.resolve(),
        models_dir=args.models_dir.resolve(),
        screenshots_dir=args.screenshots_dir.resolve(),
        headless=not args.no_headless,
        pause=args.pause,
        skip_export=args.skip_export,
        skip_render=args.skip_render,
    )


if __name__ == "__main__":
    main()
