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


if __name__ == "__main__":
    unittest.main()
