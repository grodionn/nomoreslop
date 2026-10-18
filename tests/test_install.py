import importlib.util
from pathlib import Path
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

    def test_project_cli_uses_repo_scoped_discovery_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(SCRIPT), "--project", directory],
                text=True, encoding="utf-8", capture_output=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(directory) / ".agents" / "skills" / "nomoreslop-design" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
