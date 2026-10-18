#!/usr/bin/env python3
"""Entry point for python -m tcv_screenshots."""

import argparse
import sys
from pathlib import Path

from .render import BROWSERS, check_browsers, run


def main():
    parser = argparse.ArgumentParser(
        prog="tcv_screenshots",
        description="Generate screenshots from CAD examples using three-cad-viewer"
    )

    # Input source (mutually exclusive); not needed with --check
    input_group = parser.add_mutually_exclusive_group()
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
        "--no-gpu",
        action="store_true",
        help="Render with the software renderer SwiftShader instead of the GPU: "
        "works without a GPU (CI), but is much slower for large models",
    )
    parser.add_argument(
        "--browser",
        choices=BROWSERS,
        help="Use this browser only: an installed Google Chrome or Microsoft Edge, "
        "or chromium, Playwright's own (`playwright install chromium`). "
        "Default: the first that works of msedge, chrome, chromium on Windows "
        "and chrome, msedge, chromium elsewhere",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Show which browsers work, with version and renderer, and which one "
        "a run would use; renders nothing",
    )
    parser.add_argument(
        "--debug",
        type=Path,
        metavar="MODELS_DIR",
        help="Save JSON model files to this directory, show browser console "
        "messages and full rendering errors (for debugging)",
    )

    args = parser.parse_args()

    if args.check:
        usable = check_browsers(gpu=not args.no_gpu, browser=args.browser)
        sys.exit(0 if usable else 1)

    if args.file is None and args.directory is None:
        parser.error("one of the arguments -f/--file -d/--directory is required")

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
        gpu=not args.no_gpu,
        browser=args.browser,
    )


if __name__ == "__main__":
    main()
