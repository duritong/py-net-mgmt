import os
import shutil
import tempfile
import unittest
import unittest.mock

from click.testing import CliRunner

from net_mgmt.cli import cli


class TestCliList(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_dir = tempfile.mkdtemp()
        self.networks_dir = os.path.join(self.test_dir, "networks")
        os.makedirs(self.networks_dir)

        self.network_file = os.path.join(self.networks_dir, "test_net.yaml")
        with open(self.network_file, "w") as f:
            f.write("""
cidr: 192.168.100.0/24
vlan: 10
description: Test Network Description
datacenter: DC1
zone: dmz
context: production
default_mtu: 1500
""")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_list_output(self):
        result = self.runner.invoke(cli, ["list", "--path", self.networks_dir])
        if result.exit_code != 0:
            print(result.output)
        self.assertEqual(result.exit_code, 0)
        output = result.output

        # Verify headers are in output
        self.assertIn("Name", output)
        self.assertIn("CIDR", output)
        self.assertIn("Context", output)
        self.assertIn("Datacenter", output)
        self.assertIn("Zone", output)
        self.assertIn("MTU", output)
        self.assertIn("Description", output)

        # Verify network details are in output
        self.assertIn("test_net", output)
        self.assertIn("192.168.100.0/24", output)
        self.assertIn("production", output)
        self.assertIn("DC1", output)
        self.assertIn("dmz", output)
        self.assertIn("1500", output)
        self.assertIn("Test Network Description", output)

    def test_list_with_description_filter(self):
        # 1. Matching filter (case-insensitive substring) -> should list the network
        result = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--description", "network"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test_net", result.output)
        self.assertIn("Test Network Description", result.output)

        # 2. Non-matching filter -> should output No matching networks found
        result2 = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--description", "nonexistent"])
        self.assertEqual(result2.exit_code, 0)
        self.assertIn("No matching networks found.", result2.output)

    def test_list_with_coordinate_filters(self):
        # 1. Matching VLAN ID -> should list
        result1 = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--vlan", "10"])
        self.assertEqual(result1.exit_code, 0)
        self.assertIn("test_net", result1.output)

        # 2. Non-matching VLAN ID -> should output No matching networks found
        result2 = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--vlan", "999"])
        self.assertEqual(result2.exit_code, 0)
        self.assertIn("No matching networks found.", result2.output)

        # 3. Matching Datacenter -> should list
        result3 = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--dc", "DC1"])
        self.assertEqual(result3.exit_code, 0)
        self.assertIn("test_net", result3.output)

        # 4. Non-matching Datacenter -> should output No matching networks found
        result4 = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--dc", "DC2"])
        self.assertEqual(result4.exit_code, 0)
        self.assertIn("No matching networks found.", result4.output)

        # 5. Matching CIDR -> should list
        result5 = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--cidr", "192.168.100.0/24"])
        self.assertEqual(result5.exit_code, 0)
        self.assertIn("test_net", result5.output)

        # 6. Non-matching CIDR -> should output No matching networks found
        result6 = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--cidr", "10.0.0.0/24"])
        self.assertEqual(result6.exit_code, 0)
        self.assertIn("No matching networks found.", result6.output)

        # 7. Matching IP containment -> should list
        result7 = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--ip", "192.168.100.50"])
        self.assertEqual(result7.exit_code, 0)
        self.assertIn("test_net", result7.output)

        # 8. Non-matching IP containment -> should output No matching networks found
        result8 = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--ip", "10.0.1.100"])
        self.assertEqual(result8.exit_code, 0)
        self.assertIn("No matching networks found.", result8.output)

    def test_list_with_no_wrap(self):
        # Assert the CLI accepts the --no-wrap flag without errors
        result = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--no-wrap"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test_net", result.output)

    def test_list_formats(self):
        # 1. Test JSON format
        result_json = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--format", "json"])
        self.assertEqual(result_json.exit_code, 0)
        self.assertIn("192.168.100.0/24", result_json.output)
        self.assertIn('"name": "test_net"', result_json.output)

        # 2. Test CSV format
        result_csv = self.runner.invoke(cli, ["list", "--path", self.networks_dir, "--format", "csv"])
        self.assertEqual(result_csv.exit_code, 0)
        self.assertIn("Name,CIDR,Context,Datacenter,Zone,Environment,MTU,Description", result_csv.output)
        self.assertIn("test_net,192.168.100.0/24", result_csv.output)


class TestCliListEmpty(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_dir = tempfile.mkdtemp()
        self.networks_dir = os.path.join(self.test_dir, "networks")
        os.makedirs(self.networks_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_list_empty(self):
        result = self.runner.invoke(cli, ["list", "--path", self.networks_dir])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No networks found.", result.output)


class TestCliEdit(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_dir = tempfile.mkdtemp()
        self.networks_dir = os.path.join(self.test_dir, "networks")
        os.makedirs(self.networks_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @unittest.mock.patch("subprocess.run")
    def test_edit_network_legacy(self, mock_run):
        # Create a network file
        net_file = os.path.join(self.networks_dir, "test_net.yaml")
        with open(net_file, "w") as f:
            f.write("cidr: 10.0.0.0/24")

        # Mock env EDITOR
        import os as local_os

        with unittest.mock.patch.dict(local_os.environ, {"EDITOR": "nano"}):
            result = self.runner.invoke(cli, ["edit", "network", "test_net", "--path", self.networks_dir])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Opening", result.output)
            self.assertIn("nano", result.output)
            mock_run.assert_called_once_with(["nano", net_file], check=True)

    @unittest.mock.patch("subprocess.run")
    def test_edit_network_relational(self, mock_run):
        # Create relational folder structure
        os.makedirs(os.path.join(self.test_dir, "epgs"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "networks"), exist_ok=True)

        epg_file = os.path.join(self.test_dir, "epgs", "EPG_App.yaml")
        with open(epg_file, "w") as f:
            f.write("vlan: 10")

        # Mock env EDITOR
        import os as local_os

        with unittest.mock.patch.dict(local_os.environ, {"EDITOR": "vim"}):
            result = self.runner.invoke(cli, ["edit", "epg", "EPG_App", "--path", self.test_dir])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Opening", result.output)
            self.assertIn("vim", result.output)
            mock_run.assert_called_once_with(["vim", epg_file], check=True)


class TestCliFormat(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_format_ordering_and_comment_preservation(self):
        # 1. Setup a poorly ordered yaml file with various comments
        yaml_content = """# Document Leading Comment
vlan: 10
cidr: 10.0.0.0/24
# Relation Comment
datacenter: DC1
# Description Comment
description: "Test Network Description"
context: production
# Allocations Comment
allocations:
  - ip: 10.0.0.12 # Host 2 Comment
    hostname: host2
  # Host 1 Comment
  - ip: 10.0.0.6
    hostname: host1
# Reservations Comment
reservations:
  - id: pool2
    cidr: 10.0.0.64/28
    allocatable: true
  - id: pool1
    cidr: 10.0.0.0/28
    allocatable: true
"""
        networks_dir = os.path.join(self.test_dir, "networks")
        os.makedirs(networks_dir)
        net_file = os.path.join(networks_dir, "test_net.yaml")
        with open(net_file, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        # 2. Run format for the first time -> should format 1 file
        result1 = self.runner.invoke(cli, ["format", "--path", networks_dir])
        self.assertEqual(result1.exit_code, 0)
        self.assertIn("Formatted: 1 file(s)", result1.output)

        # 3. Read the formatted content and verify ordering
        with open(net_file, "r", encoding="utf-8") as f:
            formatted_content = f.read()

        # Let's inspect the exact lines to ensure:
        # - cidr is first
        # - description is second
        # - datacenter is third (relations)
        # - vlan/context are next (alphabetical)
        # - reservations are next (sorted by IP)
        # - allocations are last (sorted by IP)
        lines = [line.strip() for line in formatted_content.splitlines() if line.strip()]

        # cidr should appear before description
        cidr_idx = [i for i, line in enumerate(lines) if "cidr:" in line][0]
        desc_idx = [i for i, line in enumerate(lines) if "description:" in line][0]
        self.assertTrue(cidr_idx < desc_idx)

        # description should appear before datacenter
        dc_idx = [i for i, line in enumerate(lines) if "datacenter:" in line][0]
        self.assertTrue(desc_idx < dc_idx)

        # datacenter should appear before vlan
        vlan_idx = [i for i, line in enumerate(lines) if "vlan:" in line][0]
        self.assertTrue(dc_idx < vlan_idx)

        # reservations should come before allocations
        res_idx = [i for i, line in enumerate(lines) if "reservations:" in line][0]
        alloc_idx = [i for i, line in enumerate(lines) if "allocations:" in line][0]
        self.assertTrue(res_idx < alloc_idx)

        # Verify reservations are sorted (pool1: 10.0.0.0/28 before pool2: 10.0.0.64/28)
        p1_idx = [i for i, line in enumerate(lines) if "id: pool1" in line][0]
        p2_idx = [i for i, line in enumerate(lines) if "id: pool2" in line][0]
        self.assertTrue(p1_idx < p2_idx)

        # Verify allocations are sorted (host1: 10.0.0.5 before host2: 10.0.0.12)
        h1_idx = [i for i, line in enumerate(lines) if "hostname: host1" in line][0]
        h2_idx = [i for i, line in enumerate(lines) if "hostname: host2" in line][0]
        self.assertTrue(h1_idx < h2_idx)

        # Verify key comments are preserved
        self.assertIn("# Document Leading Comment", formatted_content)
        self.assertIn("# Relation Comment", formatted_content)
        self.assertIn("# Description Comment", formatted_content)
        self.assertIn("# Reservations Comment", formatted_content)
        self.assertIn("# Allocations Comment", formatted_content)
        self.assertIn("# Host 1 Comment", formatted_content)
        self.assertIn("Host 2 Comment", formatted_content)

        # 4. Run format for a second time -> should skip (Strict Idempotency!)
        result2 = self.runner.invoke(cli, ["format", "--path", networks_dir])
        self.assertEqual(result2.exit_code, 0)
        self.assertIn("Formatted: 0 file(s)", result2.output)
        self.assertIn("Skipped: 1 file(s)", result2.output)

    def test_format_safety_and_validate_format_delegation(self):
        # 1. Setup a directory with overlapping CIDR validation errors
        networks_dir = os.path.join(self.test_dir, "networks_invalid")
        os.makedirs(networks_dir)

        # Write overlapping subnets (which triggers ValueError during get_database())
        with open(os.path.join(networks_dir, "net1.yaml"), "w") as f:
            f.write("cidr: 10.0.0.0/24\n")
        with open(os.path.join(networks_dir, "net2.yaml"), "w") as f:
            f.write("cidr: 10.0.0.0/24\n")  # Overlap!

        # 2. Assert format command FAILS and exits with non-zero when validation fails!
        result_fmt = self.runner.invoke(cli, ["format", "--path", networks_dir])
        self.assertNotEqual(result_fmt.exit_code, 0)
        self.assertIn("Format Error: Cannot format because database contains validation errors", result_fmt.output)

        # 3. Assert validate --format also fails immediately and does not format
        result_val_err = self.runner.invoke(cli, ["validate", "--path", networks_dir, "--format"])
        self.assertNotEqual(result_val_err.exit_code, 0)
        self.assertIn("Validation Error", result_val_err.output)

        # 4. Resolve the validation issue
        with open(os.path.join(networks_dir, "net2.yaml"), "w") as f:
            f.write("""# DC Info Comment
datacenter: DC1
cidr: 10.0.1.0/24  # Valid now
# Description Comment
description: "Net 2"
""")

        # 5. Assert validate --format now succeeds AND formats the resolved file successfully!
        result_val_ok = self.runner.invoke(cli, ["validate", "--path", networks_dir, "--format"])
        self.assertEqual(result_val_ok.exit_code, 0)
        self.assertIn("Successfully validated 2 networks.", result_val_ok.output)
        self.assertIn("Format complete. Formatted: 1 file(s)", result_val_ok.output)

        # 6. Read net2.yaml and verify that it was formatted (cidr comes first, then description, then datacenter!)
        with open(os.path.join(networks_dir, "net2.yaml"), "r") as f:
            net2_content = f.read()

        lines = [line.strip() for line in net2_content.splitlines() if line.strip()]
        cidr_idx = [i for i, line in enumerate(lines) if "cidr:" in line][0]
        desc_idx = [i for i, line in enumerate(lines) if "description:" in line][0]
        dc_idx = [i for i, line in enumerate(lines) if "datacenter:" in line][0]
        self.assertTrue(cidr_idx < desc_idx)
        self.assertTrue(desc_idx < dc_idx)


if __name__ == "__main__":
    unittest.main()
