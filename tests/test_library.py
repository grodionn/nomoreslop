"""Exercise the public CLI and reject damaged, independently copied packages."""

from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "nomoreslop-design"
SPEC = importlib.util.spec_from_file_location("design_library", SKILL / "scripts" / "library.py")
library = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = library
SPEC.loader.exec_module(library)


def fingerprint(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts
    }


@contextmanager
def isolated_package():
    with tempfile.TemporaryDirectory(prefix="nomoreslop-") as directory:
        root = Path(directory) / "a folder with spaces" / "nomoreslop-design"
        shutil.copytree(SKILL, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        with patch.object(library, "ROOT", root), patch.object(library, "REFERENCES", root / "references"):
            yield root


def cli(*args, root=SKILL, cwd=REPO):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(root / "scripts" / "library.py"), *args],
        cwd=cwd, text=True, encoding="utf-8", capture_output=True, timeout=30,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
    )


class LibraryTests(unittest.TestCase):
    def test_distributed_package_is_valid(self):
        self.assertEqual(library.validate(library.load_records()), [])

    def test_start_contains_complete_selected_records_only(self):
        result = cli("start")
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = library.HEADING.findall(result.stdout)
        self.assertEqual([heading[0] for heading in actual], list(library.START_IDS))
        for record in library.load_records():
            if record.identifier in library.START_IDS:
                self.assertIn(record.body, result.stdout)

    def test_show_preserves_order_deduplicates_and_accepts_lowercase(self):
        result = cli("show", "mat-01", "TXT-03", "MAT-01")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([h[0] for h in library.HEADING.findall(result.stdout)], ["MAT-01", "TXT-03"])

    def test_unknown_id_fails_before_printing_partial_results(self):
        result = cli("show", "TXT-01", "UNKNOWN-99")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("UNKNOWN-99", result.stderr)

    def test_missing_command_is_an_error(self):
        self.assertNotEqual(cli().returncode, 0)

    def test_cli_works_after_copy_from_an_unrelated_directory(self):
        with isolated_package() as root, tempfile.TemporaryDirectory() as directory:
            result = cli("check", root=root, cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_read_commands_do_not_mutate_the_package(self):
        with isolated_package() as root:
            before = fingerprint(root)
            for args in [("start",), ("show", "TXT-01"), ("index", "technique"), ("check",), ("stats",)]:
                result = cli(*args, root=root)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(fingerprint(root), before)

    def test_statistics_are_machine_readable_without_optional_dependencies(self):
        result = cli("stats")
        self.assertEqual(result.returncode, 0, result.stderr)
        stats = json.loads(result.stdout)
        records = library.load_records()
        self.assertEqual(stats["antipatterns"], sum(r.kind == "antipattern" for r in records))
        self.assertEqual(stats["techniques"], sum(r.kind == "technique" for r in records))
        self.assertIsNone(stats["encoding"])
        self.assertNotIn("tokens", stats["packets"]["core"])
        self.assertGreater(stats["packets"]["new_ui_start"]["characters"], stats["packets"]["core"]["characters"])

    def test_stale_index_is_rejected_and_regeneration_is_idempotent(self):
        with isolated_package() as root:
            index = root / "references" / "antipattern-index.md"
            index.write_text("outdated\n", encoding="utf-8")
            self.assertTrue(library.validate(library.load_records()))
            self.assertEqual(cli("build-index", root=root).returncode, 0)
            self.assertEqual(library.validate(library.load_records()), [])
            before = fingerprint(root)
            self.assertEqual(cli("build-index", root=root).returncode, 0)
            self.assertEqual(fingerprint(root), before)

    def test_broken_local_reference_is_rejected(self):
        with isolated_package() as root:
            (root / "checks" / "broken.md").write_text("[missing](missing-file.md)\n", encoding="utf-8")
            self.assertTrue(any("Broken local link" in e for e in library.validate(library.load_records())))

    def test_reference_outside_the_package_is_rejected(self):
        with isolated_package() as root:
            (root / "checks" / "escape.md").write_text("[outside](../../secret.md)\n", encoding="utf-8")
            self.assertTrue(any("Link escapes package" in e for e in library.validate(library.load_records())))

    def test_unknown_record_reference_is_rejected(self):
        with isolated_package() as root:
            (root / "checks" / "unknown.md").write_text("See TXT-99.\n", encoding="utf-8")
            self.assertTrue(any("Unknown record reference" in e for e in library.validate(library.load_records())))

    def test_duplicate_identifier_is_rejected(self):
        with isolated_package() as root:
            path = root / "references" / "antipatterns" / "text.md"
            text = path.read_text(encoding="utf-8").replace("### TXT-02", "### TXT-01", 1)
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate identifier"):
                library.load_records()

    def test_missing_required_record_field_is_rejected(self):
        with isolated_package() as root:
            path = root / "references" / "antipatterns" / "text.md"
            text = re.sub(r"^Граница:.*(?:\n|$)", "", path.read_text(encoding="utf-8"), count=1, flags=re.M)
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Граница"):
                library.load_records()

    def test_invalid_status_is_rejected(self):
        with isolated_package() as root:
            path = root / "references" / "antipatterns" / "text.md"
            text = re.sub(r"(### TXT-01[^\n]*?) \[[ДКУ]\]", r"\1", path.read_text(encoding="utf-8"), count=1)
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid status"):
                library.load_records()

    def test_damaged_png_is_rejected(self):
        with isolated_package() as root:
            image_folder = root / "references" / "examples"
            image_folder.mkdir(parents=True, exist_ok=True)
            (image_folder / "synthetic-invalid.png").write_bytes(b"not a PNG")
            self.assertTrue(any("Invalid PNG" in e for e in library.validate(library.load_records())))

    def test_core_context_budget_is_enforced(self):
        with isolated_package() as root:
            path = root / "SKILL.md"
            path.write_text(path.read_text(encoding="utf-8") + "x" * library.CORE_CHAR_BUDGET, encoding="utf-8")
            self.assertTrue(any("Core exceeds" in e for e in library.validate(library.load_records())))


if __name__ == "__main__":
    unittest.main()
