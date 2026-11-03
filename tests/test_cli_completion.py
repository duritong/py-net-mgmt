import shutil
import subprocess
import unittest

from click.testing import CliRunner

from net_mgmt.cli import cli


class TestCliCompletion(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_completion_default_is_bash(self):
        result = self.runner.invoke(cli, ["completion"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("_net_mgmt_completion", result.output)
        self.assertIn("complete -o nosort -F _net_mgmt_completion net-mgmt", result.output)

    def test_completion_bash_syntax(self):
        result = self.runner.invoke(cli, ["completion", "bash"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("_net_mgmt_completion", result.output)
        if shutil.which("bash"):
            proc = subprocess.run(
                ["bash", "-n"],
                input=result.output,
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, f"Bash syntax check failed: {proc.stderr}")

    def test_completion_zsh(self):
        result = self.runner.invoke(cli, ["completion", "zsh"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("#compdef net-mgmt", result.output)

    def test_completion_fish(self):
        result = self.runner.invoke(cli, ["completion", "fish"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("function _net_mgmt_completion", result.output)

    def test_completion_invalid_shell(self):
        result = self.runner.invoke(cli, ["completion", "unsupported_shell"])
        self.assertNotEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
