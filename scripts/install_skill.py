#!/usr/bin/env python3
"""Copy the self-contained skill into a discoverable directory without overwriting."""

import argparse
from pathlib import Path
import shutil
import sys


SOURCE = Path(__file__).resolve().parents[1] / "skills" / "nomoreslop-design"


def install(destination):
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists; inspect it before updating: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    destinations = parser.add_mutually_exclusive_group()
    destinations.add_argument("--project", type=Path, help="Install under PROJECT/.agents/skills")
    destinations.add_argument("--dest", type=Path, help="Exact destination folder, including nomoreslop-design")
    args = parser.parse_args()
    if args.dest is not None:
        destination = args.dest
    elif args.project is not None:
        destination = args.project / ".agents" / "skills" / "nomoreslop-design"
    else:
        destination = Path.home() / ".agents" / "skills" / "nomoreslop-design"
    try:
        print(f"Installed: {install(destination)}")
    except OSError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
