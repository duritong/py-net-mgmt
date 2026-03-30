import os
import shutil
import tempfile
import unittest

from click.testing import CliRunner

from net_mgmt.cli import cli


class TestCliMarkdownOutput(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_dir = tempfile.mkdtemp()
        self.networks_dir = os.path.join(self.test_dir, "networks")
        os.makedirs(self.networks_dir)
        self.custom_output = os.path.join(self.test_dir, "custom_report.md")

        self.network_file = os.path.join(self.networks_dir, "test_net.yaml")
        with open(self.network_file, "w") as f:
            f.write("cidr: 192.168.100.0/24")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_generate_markdown_custom_output(self):
        result = self.runner.invoke(cli, ["generate-markdown", "--path", self.networks_dir, "-o", self.custom_output])
        if result.exit_code != 0:
            print(result.output)
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.exists(self.custom_output))

        with open(self.custom_output, "r") as f:
            content = f.read()
        self.assertIn("# Network Overview", content)
        self.assertIn("| Context |", content)
        self.assertIn("| test_net | 192.168.100.0/24 | default |", content)
        self.assertIn("- **Context**: `default`", content)


if __name__ == "__main__":
    unittest.main()
