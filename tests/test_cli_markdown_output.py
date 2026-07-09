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
        self.custom_output_dir = os.path.join(self.test_dir, "custom_report")

        self.network_file = os.path.join(self.networks_dir, "test_net.yaml")
        with open(self.network_file, "w") as f:
            f.write("cidr: 192.168.100.0/24")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_generate_markdown_custom_output(self):
        result = self.runner.invoke(
            cli, ["generate-markdown", "--path", self.networks_dir, "-o", self.custom_output_dir]
        )
        if result.exit_code != 0:
            print(result.output)
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(os.path.exists(self.custom_output_dir))

        readme_path = os.path.join(self.custom_output_dir, "README.md")
        self.assertTrue(os.path.exists(readme_path))

        with open(readme_path, "r") as f:
            readme_content = f.read()
        self.assertIn("# Network Overview", readme_content)
        self.assertIn("| Context |", readme_content)
        self.assertIn("[test_net](test_net.md) | 192.168.100.0/24 | default |", readme_content)

        net_path = os.path.join(self.custom_output_dir, "test_net.md")
        self.assertTrue(os.path.exists(net_path))

        with open(net_path, "r") as f:
            net_content = f.read()
        self.assertIn("# test_net", net_content)
        self.assertIn("- **Context**: `default`", net_content)


if __name__ == "__main__":
    unittest.main()
