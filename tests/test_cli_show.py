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
        result = self.runner.invoke(cli, ["show", "networks", "test_net", "--path", self.networks_dir])
        if result.exit_code != 0:
            print(result.output)
        self.assertEqual(result.exit_code, 0)

        self.assertIn("Reserve Gateway: True", result.output)
        self.assertIn("Context: default", result.output)
        self.assertIn("Reserve Internal: True", result.output)
        self.assertIn("Reserve Internal Until: 6", result.output)
        self.assertIn("Allocations", result.output)
        self.assertIn("192.168.100.16/28", result.output)
        self.assertIn("Subnet 1", result.output)
        self.assertIn("Usage", result.output)
        self.assertIn("9.4%", result.output)
        self.assertIn("Unreserved Ranges:", result.output)
        self.assertIn("192.168.100.7 - 192.168.100.9", result.output)

    def test_show_formats(self):
        # 1. Test JSON format
        result_json = self.runner.invoke(
            cli, ["show", "networks", "test_net", "--format", "json", "--path", self.networks_dir]
        )
        self.assertEqual(result_json.exit_code, 0)
        self.assertIn('"cidr": "192.168.100.0/24"', result_json.output)
        self.assertIn('"reservations":', result_json.output)
        self.assertIn('"allocations":', result_json.output)

        # 2. Test CSV format
        result_csv = self.runner.invoke(
            cli, ["show", "networks", "test_net", "--format", "csv", "--path", self.networks_dir]
        )
        self.assertEqual(result_csv.exit_code, 0)
        self.assertIn("Type,ID_Hostname,CIDR_IP,Comment,Allocatable", result_csv.output)
        self.assertIn("reservation,pool1,192.168.100.10-192.168.100.200", result_csv.output)
        self.assertIn("allocation,host1,192.168.100.10", result_csv.output)

    def test_show_levels(self):
        # Setup relational files inside self.test_dir
        os.makedirs(os.path.join(self.test_dir, "datacenters"), exist_ok=True)
        with open(os.path.join(self.test_dir, "datacenters", "DC1.yaml"), "w") as f:
            f.write("timeservers:\n  - 1.1.1.1\ndns_nameservers:\n  - 8.8.8.8\n")

        # 1. Test showing a datacenter
        result = self.runner.invoke(cli, ["show", "datacenters", "DC1", "--path", self.test_dir])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Name: DC1", result.output)
        self.assertIn("Timeservers: 1.1.1.1", result.output)
        self.assertIn("DNS Nameservers: 8.8.8.8", result.output)

        # 2. Test aliases
        result_alias = self.runner.invoke(cli, ["show", "dc", "DC1", "--path", self.test_dir])
        self.assertEqual(result_alias.exit_code, 0)
        self.assertIn("Name: DC1", result_alias.output)

        # 3. Test format json
        result_json = self.runner.invoke(cli, ["show", "dc", "dc1", "--format", "json", "--path", self.test_dir])
        self.assertEqual(result_json.exit_code, 0)
        self.assertIn('"name": "DC1"', result_json.output)


if __name__ == "__main__":
    unittest.main()
