import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "install_skill.py"
SPEC = importlib.util.spec_from_file_location("install_skill", SCRIPT)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_installs_a_self_contained_package_to_a_path_with_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "my skills" / "nomoreslop-design"
            installer.install(destination)
            self.assertTrue((destination / "SKILL.md").is_file())
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(destination / "scripts" / "library.py"), "check"],
                cwd=directory, text=True, encoding="utf-8", capture_output=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "nomoreslop-design"
            destination.mkdir()
            marker = destination / "SKILL.md"
            marker.write_text("local modifications", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                installer.install(destination)
            self.assertEqual(marker.read_text(encoding="utf-8"), "local modifications")
            self.assertEqual(list(destination.iterdir()), [marker])

    def test_3d_install_preserves_supporting_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "my skills" / "nomoreslop-3d"
            installer.install(destination, "nomoreslop-3d")
            source = REPO / "skills" / "nomoreslop-3d"
            expected = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
            actual = {p.relative_to(destination): p.read_bytes() for p in destination.rglob("*") if p.is_file()}
            self.assertEqual(actual, expected)
            self.assertTrue((destination / "references" / "runtime-and-delivery.md").is_file())

    def test_project_cli_uses_repo_scoped_discovery_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(SCRIPT), "--project", directory],
                text=True, encoding="utf-8", capture_output=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(directory) / ".agents" / "skills" / "nomoreslop-design" / "SKILL.md").is_file())

    def test_api_rejects_unknown_or_traversing_skill_names_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "unexpected-parent" / "skill"
            for skill in ("../nomoreslop-design", "..\\nomoreslop-design", "other"):
                with self.subTest(skill=skill), self.assertRaises(ValueError):
                    installer.install(destination, skill)
            self.assertFalse(destination.parent.exists())

    def test_cli_selects_new_skills_and_refuses_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "scripts" / SCRIPT.name
            script.parent.mkdir()
            shutil.copyfile(SCRIPT, script)
            for skill in ("nomoreslop-writing", "nomoreslop-3d", "nomoreslop"):
                with self.subTest(skill=skill):
                    source = root / "skills" / skill
                    source.mkdir(parents=True)
                    (source / "SKILL.md").write_text(skill, encoding="utf-8")
                    command = [sys.executable, "-X", "utf8", str(script), "--skill", skill, "--project", str(root / "project")]
                    result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    destination = root / "project" / ".agents" / "skills" / skill
                    marker = destination / "SKILL.md"
                    self.assertEqual(marker.read_text(encoding="utf-8"), skill)
                    marker.write_text("local modifications", encoding="utf-8")
                    result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, timeout=30)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("Destination already exists", result.stderr)
                    self.assertEqual(marker.read_text(encoding="utf-8"), "local modifications")


if __name__ == "__main__":
    unittest.main()
