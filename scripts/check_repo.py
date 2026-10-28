#!/usr/bin/env python3
"""Check local documentation links. No network, third-party dependencies or writes."""

from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".local", ".venv", "node_modules", "__pycache__", "test-results", "playwright-report"}
LINK = re.compile(r"!?\[[^\]\n]*\]\((<[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\)")
TEXT_SUFFIXES = {".md", ".py", ".yml", ".yaml"}
ROOT_FILES = {".editorconfig", ".gitattributes", ".gitignore", "LICENSE"}
SKILL_DATA_FILES = {
    "skills/nomoreslop-design/references/pattern-checks.json",
    "skills/nomoreslop-design/references/source-adapters.json",
    "skills/nomoreslop-typography/references/font-sources.json",
}
PRIVATE_PREFIXES = (".local/", "node_modules/", "evals/", "examples/", "docs/assets/")


def check_distribution_paths(paths):
    errors = []
    for name in paths:
        path = Path(name)
        if name.startswith(PRIVATE_PREFIXES):
            errors.append(f"Internal or unreviewed material is tracked: {name}")
        elif name not in ROOT_FILES | SKILL_DATA_FILES and path.suffix not in TEXT_SUFFIXES:
            errors.append(f"File outside the text-only package: {name}")
    return errors


def tracked_paths(root):
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "-z"],
            capture_output=True, check=True, timeout=15,
        )
        return [name for name in result.stdout.decode("utf-8").split("\0") if name]
    except (OSError, subprocess.SubprocessError):
        return [
            source.relative_to(root).as_posix()
            for source in root.rglob("*")
            if source.is_file() and not EXCLUDED.intersection(source.relative_to(root).parts)
        ]


def check(root=ROOT):
    errors = check_distribution_paths(tracked_paths(root))
    for source in sorted(root.rglob("*.md")):
        if EXCLUDED.intersection(source.relative_to(root).parts):
            continue
        content = source.read_text(encoding="utf-8")
        # Examples inside code fences describe generated files, not repository links.
        content = re.sub(r"(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1\s*$", "", content)
        for match in LINK.finditer(content):
            link = match.group(1).strip("<>")
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            destination = (source.parent / unquote(parsed.path)).resolve()
            relative = source.relative_to(root).as_posix()
            if not destination.is_relative_to(root):
                errors.append(f"{relative}: link leaves repository: {link}")
            elif not destination.exists():
                errors.append(f"{relative}: broken link: {link}")
        if "\ufffd" in content:
            errors.append(f"{source.relative_to(root)}: invalid Unicode replacement character")
    return errors


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    failures = check()
    for failure in failures:
        print(f"ERROR: {failure}", file=sys.stderr)
    if not failures:
        print("OK: documentation links resolve; tracked files match the text-only package.")
    raise SystemExit(bool(failures))
