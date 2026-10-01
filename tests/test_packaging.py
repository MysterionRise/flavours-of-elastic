"""requirements*.txt (the course's plain-pip path) must match pyproject.toml (uv)."""

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def requirements(name: str) -> list:
    lines = (ROOT / name).read_text(encoding="utf-8").splitlines()
    return [
        line.split("#")[0].strip()
        for line in lines
        if line.strip() and not line.startswith(("#", "-r"))
    ]


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.project = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )

    def test_runtime_dependencies(self):
        self.assertEqual(
            requirements("requirements.txt"), self.project["project"]["dependencies"]
        )

    def test_demo_extra(self):
        self.assertEqual(
            requirements("requirements-demo.txt"),
            self.project["project"]["optional-dependencies"]["demo"],
        )

    def test_dev_group(self):
        self.assertEqual(
            requirements("requirements-dev.txt"),
            self.project["dependency-groups"]["dev"],
        )

    def test_console_scripts_exist(self):
        import importlib

        for target in self.project["project"]["scripts"].values():
            module, function = target.split(":")
            self.assertTrue(
                callable(getattr(importlib.import_module(module), function)), target
            )

    def test_lock_file_is_committed(self):
        self.assertIn(
            'name = "flavours-of-elastic"',
            (ROOT / "uv.lock").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
