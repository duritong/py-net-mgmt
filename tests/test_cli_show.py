import os
import shutil
import tempfile
import unittest

from click.testing import CliRunner

from net_mgmt.cli import cli


class TestCliShow(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_dir = tempfile.mkdtemp()
        self.networks_dir = os.path.join(self.test_dir, "networks")
        os.makedirs(self.networks_dir)

        self.network_file = os.path.join(self.networks_dir, "test_net.yaml")
        with open(self.network_file, "w") as f:
            f.write("""
cidr: 192.168.100.0/24
reservations:
  - id: pool1
    cidr: 192.168.100.10-192.168.100.200
    comment: "Pool 1"
    allocatable: true
allocations:
  - ip: 192.168.100.10
    hostname: host1
  - ip: 192.168.100.11
    hostname: host2
  - cidr: 192.168.100.16/28
    comment: "Subnet 1"
""")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_show_output(self):
        result = self.runner.invoke(cli, ["show", "test_net", "--path", self.networks_dir])
        if result.exit_code != 0:
            print(result.output)
        self.assertEqual(result.exit_code, 0)

        self.assertIn("Reserve Gateway: True", result.output)
        self.assertIn("Context: default", result.output)
        self.assertIn("Reserve Internal: True", result.output)
        self.assertIn("Allocations", result.output)
        self.assertIn("192.168.100.16/28", result.output)
        self.assertIn("Subnet 1", result.output)
        self.assertIn("Usage", result.output)
        self.assertIn("9.4%", result.output)
        self.assertIn("Unreserved Ranges:", result.output)
        self.assertIn("192.168.100.6/31", result.output)


if __name__ == "__main__":
    unittest.main()
