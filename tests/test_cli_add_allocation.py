import os
import shutil
import tempfile
import unittest

from click.testing import CliRunner

from net_mgmt.cli import cli
from net_mgmt.loader import load_network_from_file


class TestAddAllocation(unittest.TestCase):
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
  - id: res1
    cidr: 192.168.100.10-192.168.100.20
    comment: "Allocatable range"
    allocatable: true
  - id: res2
    cidr: 192.168.100.50
    comment: "Static"
    allocatable: false
""")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_add_allocation_success(self):
        result = self.runner.invoke(
            cli,
            [
                "add-allocation",
                "test_net",
                "--ip",
                "192.168.100.15",
                "--hostname",
                "host1",
                "--path",
                self.networks_dir,
            ],
        )
        if result.exit_code != 0:
            print(result.output)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Successfully added allocation", result.output)

        # Verify file content
        network = load_network_from_file(self.network_file)
        self.assertEqual(len(network.allocations), 1)
        self.assertEqual(str(network.allocations[0].ip), "192.168.100.15")
        self.assertEqual(network.allocations[0].hostname, "host1")

    def test_add_allocation_outside_reservation(self):
        # 192.168.100.30 is in CIDR but not in any allocatable reservation
        result = self.runner.invoke(
            cli,
            [
                "add-allocation",
                "test_net",
                "--ip",
                "192.168.100.30",
                "--hostname",
                "host2",
                "--path",
                self.networks_dir,
            ],
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error adding allocation", result.output)
        self.assertIn("not within any allocatable reservation", result.output)

    def test_add_allocation_duplicate(self):
        # Add first time
        self.runner.invoke(
            cli,
            [
                "add-allocation",
                "test_net",
                "--ip",
                "192.168.100.15",
                "--hostname",
                "host1",
                "--path",
                self.networks_dir,
            ],
        )
        # Add second time
        result = self.runner.invoke(
            cli,
            [
                "add-allocation",
                "test_net",
                "--ip",
                "192.168.100.15",
                "--hostname",
                "host1",
                "--path",
                self.networks_dir,
            ],
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error adding allocation", result.output)
        self.assertIn("overlaps", result.output)

    def test_add_allocation_invalid_ip(self):
        result = self.runner.invoke(
            cli,
            [
                "add-allocation",
                "test_net",
                "--ip",
                "999.999.999.999",
                "--hostname",
                "host3",
                "--path",
                self.networks_dir,
            ],
        )
        self.assertEqual(result.exit_code, 1)


if __name__ == "__main__":
    unittest.main()
