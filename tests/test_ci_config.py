import os
import unittest

import yaml


class TestCIConfig(unittest.TestCase):
    def test_dependabot_config_validity(self):
        dependabot_path = os.path.join(".github", "dependabot.yml")
        self.assertTrue(os.path.exists(dependabot_path), "dependabot.yml must exist")
        with open(dependabot_path, "r") as f:
            data = yaml.safe_load(f)

        self.assertEqual(data.get("version"), 2)
        updates = data.get("updates", [])
        self.assertIsInstance(updates, list)

        ecosystems = {u.get("package-ecosystem"): u for u in updates}
        self.assertIn("pip", ecosystems)
        self.assertIn("github-actions", ecosystems)

        for eco in ("pip", "github-actions"):
            cfg = ecosystems[eco]
            self.assertEqual(cfg.get("directory"), "/")
            self.assertEqual(cfg.get("schedule", {}).get("interval"), "weekly")

    def test_ci_workflow_python_matrix(self):
        test_path = os.path.join(".github", "workflows", "test.yml")
        self.assertTrue(os.path.exists(test_path), "test.yml must exist")
        with open(test_path, "r") as f:
            data = yaml.safe_load(f)

        matrix = data.get("jobs", {}).get("test", {}).get("strategy", {}).get("matrix", {})
        python_versions = list(matrix.get("python-version", []))
        for inc in matrix.get("include", []):
            if "python-version" in inc:
                python_versions.append(inc["python-version"])

        expected_versions = ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14", "3.15"]
        for version in expected_versions:
            self.assertIn(version, python_versions, f"Python {version} must be present in CI matrix")


if __name__ == "__main__":
    unittest.main()
