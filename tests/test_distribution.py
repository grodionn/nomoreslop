import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_repo.py"
SPEC = importlib.util.spec_from_file_location("check_repository", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class DistributionTests(unittest.TestCase):
    def test_skill_sources_docs_and_checks_are_allowed(self):
        paths = [
            "README.md", "LICENSE", ".gitignore", ".gitattributes", ".editorconfig",
            ".github/workflows/checks.yml", "skills/nomoreslop-design/SKILL.md",
            "skills/nomoreslop-design/scripts/library.py", "docs/TESTING.md",
            "skills/nomoreslop-design/references/pattern-checks.json",
            "skills/nomoreslop-design/references/source-adapters.json",
        ]
        self.assertEqual(checker.check_distribution_paths(paths), [])

    def test_tracking_ignored_private_material_is_rejected(self):
        self.assertTrue(checker.check_distribution_paths([".local/private-notes.md"]))

    def test_attachments_and_archives_are_rejected(self):
        for name in ["screen.png", "assets/font.woff", "history.bundle", "files.zip", "unreviewed.json"]:
            with self.subTest(name=name):
                self.assertTrue(checker.check_distribution_paths([name]))

    def test_unreviewed_artifact_directories_are_rejected_even_for_text(self):
        for name in ["evals/log.md", "examples/draft.md", "docs/assets/notes.md"]:
            with self.subTest(name=name):
                self.assertTrue(checker.check_distribution_paths([name]))

    def test_ignored_directories_are_pruned_before_descent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".local").mkdir()
            (root / ".local" / "private.md").write_text("[private](missing.md)", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "guide.md").write_text("[public](missing.md)", encoding="utf-8")
            actual_scandir = checker.os.scandir
            visited = []

            def observe(path):
                visited.append(Path(path))
                if Path(path).name == ".local":
                    raise OSError("ignored directory must not be opened")
                return actual_scandir(path)

            with patch.object(checker.os, "scandir", side_effect=observe):
                failures = checker.check(root)
            self.assertNotIn(root / ".local", visited)
            self.assertTrue(any("docs/guide.md: broken link" in error for error in failures))

    def test_public_scan_errors_are_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(checker.os, "scandir", side_effect=PermissionError("public scan denied")):
                with self.assertRaisesRegex(PermissionError, "public scan denied"):
                    checker.check(Path(directory))


if __name__ == "__main__":
    unittest.main()
