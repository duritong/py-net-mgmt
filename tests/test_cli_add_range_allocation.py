import os
import shutil
import tempfile
import unittest

from click.testing import CliRunner

from net_mgmt.cli import cli
from net_mgmt.loader import load_network_from_file


class TestAddRangeAllocation(unittest.TestCase):
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
    comment: "Safe pool"
    allocatable: true
""")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_add_subnet_allocation_success(self):
        result = self.runner.invoke(
            cli,
            [
                "add-allocation",
                "test_net",
                "--cidr",
                "192.168.100.16/28",
                "--comment",
                "Subnet 1",
                "--path",
                self.networks_dir,
            ],
        )
        if result.exit_code != 0:
            print(result.output)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Successfully added allocation 192.168.100.16/28", result.output)

        net = load_network_from_file(self.network_file)
        self.assertEqual(len(net.allocations), 1)
        self.assertEqual(net.allocations[0].cidr, "192.168.100.16/28")

    def test_add_range_allocation_success(self):
        result = self.runner.invoke(
            cli,
            [
                "add-allocation",
                "test_net",
                "--cidr",
                "192.168.100.50-192.168.100.60",
                "--comment",
                "Range 1",
                "--path",
                self.networks_dir,
            ],
        )
        self.assertEqual(result.exit_code, 0)

        net = load_network_from_file(self.network_file)
        self.assertEqual(len(net.allocations), 1)
        self.assertEqual(net.allocations[0].cidr, "192.168.100.50-192.168.100.60")

    def test_missing_comment_for_cidr(self):
        result = self.runner.invoke(
            cli, ["add-allocation", "test_net", "--cidr", "192.168.100.0/28", "--path", self.networks_dir]
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Comment is mandatory", result.output)

    def test_missing_hostname_for_ip(self):
        result = self.runner.invoke(
            cli, ["add-allocation", "test_net", "--ip", "192.168.100.10", "--path", self.networks_dir]
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Hostname is mandatory", result.output)

    def test_overlap_detection(self):
        # Add one range
        self.runner.invoke(
            cli,
            [
                "add-allocation",
                "test_net",
                "--cidr",
                "192.168.100.10-192.168.100.20",
                "--comment",
                "R1",
                "--path",
                self.networks_dir,
            ],
        )
        # Try overlapping
        result = self.runner.invoke(
            cli,
            [
                "add-allocation",
                "test_net",
                "--cidr",
                "192.168.100.15-192.168.100.25",
                "--comment",
                "R2",
                "--path",
                self.networks_dir,
            ],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("overlaps", result.output)


if __name__ == "__main__":
    unittest.main()
