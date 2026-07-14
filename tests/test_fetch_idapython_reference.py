from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "fetch_idapython_reference.py"


def git(directory: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=directory, check=True, stdout=subprocess.DEVNULL)


class FetchReferenceTest(unittest.TestCase):
    def test_clones_and_keeps_only_documentation_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "source"
            apidoc = repository / "src/plugins/idapython/apidoc"
            examples = repository / "src/plugins/idapython/examples"
            apidoc.mkdir(parents=True)
            examples.mkdir(parents=True)
            (apidoc / "ida_demo.py").write_text(
                '"""Demo module."""\n\ndef lookup(ea: int):\n    """Find a thing."""\n    pass\n',
                encoding="utf-8",
            )
            (repository / "src/plugins/idapython/api_contents.brief").write_text(
                "ida_demo\nida_demo.lookup\n", encoding="utf-8"
            )
            (examples / "index.md").write_text("# Examples\n", encoding="utf-8")
            git(repository, "init", "-q")
            git(repository, "add", ".")
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"],
                cwd=repository,
                check=True,
            )

            output = root / "reference"
            subprocess.run(
                ["python3", str(SCRIPT), "--repo", str(repository), "--output", str(output)],
                check=True,
            )

            stub = (output / "stubs/ida_demo.pyi").read_text(encoding="utf-8")
            self.assertIn("def lookup(ea: int):", stub)
            self.assertIn('"""Find a thing."""', stub)
            self.assertIn("    ...", stub)
            self.assertEqual((output / "symbols.txt").read_text(), "ida_demo\nida_demo.lookup\n")
            self.assertEqual(json.loads((output / "manifest.json").read_text())["stub_modules"], 1)
            self.assertFalse((output / ".git").exists())


if __name__ == "__main__":
    unittest.main()
