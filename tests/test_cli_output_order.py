import os
import shutil
import tempfile
import unittest

from click.testing import CliRunner

from net_mgmt.cli import cli


class TestCliOutputOrder(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_dir = tempfile.mkdtemp()
        self.networks_dir = os.path.join(self.test_dir, "networks")
        os.makedirs(self.networks_dir)

        self.network_file = os.path.join(self.networks_dir, "test_net.yaml")
        with open(self.network_file, "w") as f:
            f.write("""
cidr: 192.168.100.0/24
description: Test Network Description
reservations:
  - id: pool1
    cidr: 192.168.100.10
    comment: "Allocatable"
    allocatable: true
allocations:
  - ip: 192.168.100.10
    hostname: host1
""")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_show_order(self):
        result = self.runner.invoke(cli, ["show", "test_net", "--path", self.networks_dir])
        if result.exit_code != 0:
            print(result.output)
        self.assertEqual(result.exit_code, 0)
        output = result.output

        # Check Description is early (after CIDR)
        cidr_pos = output.find("CIDR:")
        desc_pos = output.find("Description:")

        self.assertNotEqual(cidr_pos, -1)
        self.assertNotEqual(desc_pos, -1)
        # Description should be after CIDR
        self.assertGreater(desc_pos, cidr_pos)

        # Check Allocations before Unreserved Ranges
        alloc_pos = output.find("Allocations:")
        unres_pos = output.find("Unreserved Ranges:")

        self.assertNotEqual(alloc_pos, -1)
        self.assertNotEqual(unres_pos, -1)

        self.assertLess(alloc_pos, unres_pos)


if __name__ == "__main__":
    unittest.main()
