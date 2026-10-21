#!/usr/bin/env python3
"""Copy a self-contained skill into a discoverable directory without overwriting."""

import argparse
from pathlib import Path
import shutil
import sys


SKILLS = ("nomoreslop-design", "nomoreslop-writing", "nomoreslop-3d", "nomoreslop")
SOURCE = Path(__file__).resolve().parents[1] / "skills"


def install(destination, skill="nomoreslop-design"):
    if skill not in SKILLS:
        raise ValueError(f"Unknown skill: {skill}")
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists; inspect it before updating: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE / skill, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", choices=SKILLS, default="nomoreslop-design", help="Skill to install (default: nomoreslop-design)")
    destinations = parser.add_mutually_exclusive_group()
    destinations.add_argument("--project", type=Path, help="Install under PROJECT/.agents/skills")
    destinations.add_argument("--dest", type=Path, help="Exact destination folder, including the skill name")
    args = parser.parse_args()
    if args.dest is not None:
        destination = args.dest
    elif args.project is not None:
        destination = args.project / ".agents" / "skills" / args.skill
    else:
        destination = Path.home() / ".agents" / "skills" / args.skill
    try:
        print(f"Installed: {install(destination, args.skill)}")
    except OSError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
