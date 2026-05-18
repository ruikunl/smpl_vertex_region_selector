from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the smpl_27554 vertex region selector desktop app.")
    parser.add_argument("--smoke-test", action="store_true", help="Construct the main window offscreen and exit.")
    parser.add_argument("--alignment-dir", type=Path, help="Open a specific alignment/demo asset directory on launch.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from .main_window import run_app
    except Exception as exc:
        print(
            "Could not start the desktop app. Install GUI dependencies with:\n"
            "  pip install -e '.[gui]'\n"
            f"\nImport error: {exc}",
            file=sys.stderr,
        )
        return 2
    return run_app(smoke_test=args.smoke_test, alignment_dir=args.alignment_dir)


if __name__ == "__main__":
    raise SystemExit(main())
