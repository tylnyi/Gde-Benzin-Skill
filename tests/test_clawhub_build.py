import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("build_clawhub", ROOT / "scripts/build_clawhub.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ClawHubBuildTests(unittest.TestCase):
    def test_build_keeps_source_mit_and_api_credits(self):
        originals = {name: (builder.SOURCE / name).read_bytes() for name in builder.FILES}
        with tempfile.TemporaryDirectory() as directory:
            out = builder.build(Path(directory) / "gde-benzin")
            self.assertIn("license: MIT-0\n", (out / "SKILL.md").read_text())
            self.assertIn("MIT No Attribution License", (out / "LICENSE").read_text())
            terms = (out / "references/api-terms.md").read_text()
            self.assertIn("https://gde-benzin.ru/", terms)
            self.assertIn("https://www.youtube.com/@d_tylnyi", terms)
            self.assertEqual((out / "scripts/gde_benzin.py").read_bytes(), originals["scripts/gde_benzin.py"])
            self.assertEqual(len([p for p in out.rglob("*") if p.is_file()]), 6)
            run = subprocess.run(["python3", str(out / "scripts/gde_benzin.py"), "--version"], capture_output=True, text=True, check=True)
            self.assertTrue(run.stdout.strip())
        self.assertEqual(originals, {name: (builder.SOURCE / name).read_bytes() for name in builder.FILES})
        self.assertTrue((ROOT / "LICENSE").read_text().startswith("MIT License"))

    def test_existing_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                builder.build(Path(directory))

    def test_source_directory_cannot_be_an_output(self):
        with self.assertRaises(ValueError):
            builder.build(builder.SOURCE)


if __name__ == "__main__":
    unittest.main()
