#!/usr/bin/env python3
"""Entry point for python -m tcv_screenshots."""

import argparse
import sys
from pathlib import Path

from .render import run


def main():
    parser = argparse.ArgumentParser(
        prog="tcv_screenshots",
        description="Generate screenshots from CAD examples using three-cad-viewer"
    )

    # Input source (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "-f", "--file",
        type=Path,
        help="Single Python example file to process",
    )
    input_group.add_argument(
        "-d", "--directory",
        type=Path,
        help="Directory containing Python example files (requires -o)",
    )

    parser.add_argument(
        "-o", "--output-folder",
        type=Path,
        help="Output directory for PNG screenshots",
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

    # Validate: -d requires -o
    if args.directory and not args.output_folder:
        parser.error("-d/--directory requires -o/--output-folder")

    # Determine input files and output directory
    if args.file:
        example_files = [args.file.resolve()]
        screenshots_dir = args.output_folder.resolve() if args.output_folder else Path.cwd()
    else:
        example_files = args.directory.resolve()
        screenshots_dir = args.output_folder.resolve()

    run(
        examples=example_files,
        screenshots_dir=screenshots_dir,
        headless=not args.no_headless,
        pause=args.pause,
        debug_models_dir=args.debug.resolve() if args.debug else None,
    )


if __name__ == "__main__":
    main()
