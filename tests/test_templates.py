import os
import shutil
import tempfile
import unittest

import yaml
from click.testing import CliRunner
from jinja2 import Environment

from src.net_mgmt.cli import cli
from src.net_mgmt.core import Network


class TestRelativeTemplates(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_relative_math_slash_25_networks(self):
        # 1. Recreate the user's exact template configuration
        template_data = {
            "required_prefix_length": 25,
            "reservations": [
                {"id": "hosts", "cidr_offset": "0.0.0.0/27", "comment": "foo", "allocatable": True},
                {"id": "tests", "cidr_offset": "0.0.0.64/27", "comment": "foo2", "allocatable": False},
            ],
        }

        # 2. Recreate network 192.168.0.0/25
        net1 = Network(name="net1", cidr="192.168.0.0/25")
        res1 = net1.apply_reservation_template(template_data)

        self.assertEqual(res1["applied"], ["hosts", "tests"])
        self.assertEqual(len(net1.reservations), 2)
        # Verify resolved CIDRs
        self.assertEqual(net1.reservations[0].cidr, "192.168.0.0/27")
        self.assertEqual(net1.reservations[1].cidr, "192.168.0.64/27")
        self.assertTrue(net1.reservations[0].allocatable)
        self.assertFalse(net1.reservations[1].allocatable)

        # 3. Recreate network 10.0.1.128/25 (non-zero host part subnet!)
        net2 = Network(name="net2", cidr="10.0.1.128/25")
        res2 = net2.apply_reservation_template(template_data)

        self.assertEqual(res2["applied"], ["hosts", "tests"])
        self.assertEqual(len(net2.reservations), 2)
        # Verify resolved CIDRs
        self.assertEqual(net2.reservations[0].cidr, "10.0.1.128/27")
        self.assertEqual(net2.reservations[1].cidr, "10.0.1.192/27")
        self.assertTrue(net2.reservations[0].allocatable)
        self.assertFalse(net2.reservations[1].allocatable)

    def test_idempotency_and_partial_rollbacks(self):
        # Create a template with 3 reservations
        template_data = {
            "required_prefix_len": 24,
            "reservations": [
                {"id": "pool1", "cidr_offset": "0.0.0.0/28", "allocatable": True},
                {"id": "pool2", "cidr_offset": "0.0.0.16/28", "allocatable": True},
                {"id": "pool3", "cidr_offset": "0.0.0.32/28", "allocatable": True},
            ],
        }

        net = Network(name="net_24", cidr="10.0.1.0/24")

        # Pre-apply pool1 and create a conflict for pool2 (existing overlapping reservation)
        net.add_reservation(id="pool1", cidr="10.0.1.0/28", comment="Pre", allocatable=True)
        net.add_reservation(id="clash_pool", cidr="10.0.1.16/28", comment="Clash", allocatable=False)

        # Apply template
        res = net.apply_reservation_template(template_data)

        # pool1 is skipped (idempotent), pool2 fails (conflict), pool3 is successfully applied (partial transaction)!
        self.assertEqual(res["applied"], ["pool3"])
        self.assertEqual(res["skipped"], ["pool1"])
        self.assertIn("pool2", res["failed"])
        self.assertIn("overlaps with", res["failed"]["pool2"])

        # Check total reservations (pool1 pre-existing + system reservations + pool3)
        res_ids = {r.id for r in net.effective_reservations}
        self.assertIn("pool1", res_ids)
        self.assertIn("pool3", res_ids)
        self.assertNotIn("pool2", res_ids)

    def test_cli_apply_template(self):
        # Setup temp DB folder
        networks_dir = os.path.join(self.temp_dir, "networks")
        os.makedirs(networks_dir)

        # Write two networks matching /25
        with open(os.path.join(networks_dir, "n1.yaml"), "w") as f:
            f.write("cidr: 192.168.0.0/25\n")
        with open(os.path.join(networks_dir, "n2.yaml"), "w") as f:
            f.write("cidr: 10.0.1.128/25\n")
        # Write one mismatch network /24
        with open(os.path.join(networks_dir, "n3.yaml"), "w") as f:
            f.write("cidr: 10.0.2.0/24\n")

        # Write template file
        template_file = os.path.join(self.temp_dir, "my_template.yaml")
        template_data = {
            "required_prefix_length": 25,
            "reservations": [{"id": "hosts", "cidr_offset": "0.0.0.0/27", "allocatable": True}],
        }
        with open(template_file, "w") as f:
            yaml.dump(template_data, f)

        runner = CliRunner()
        # Apply globally (should match n1 and n2, but skip n3!)
        result = runner.invoke(cli, ["apply-template", "--template", template_file, "--path", networks_dir])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Applying template", result.output)
        self.assertIn("n1", result.output)
        self.assertIn("n2", result.output)
        self.assertNotIn("n3", result.output)

        # Verify n1 on disk has been updated and saved successfully
        with open(os.path.join(networks_dir, "n1.yaml"), "r") as f:
            n1_data = yaml.safe_load(f)
        self.assertEqual(n1_data["reservations"][0]["id"], "hosts")
        self.assertEqual(n1_data["reservations"][0]["cidr"], "192.168.0.0/27")

    def test_jinja_filter_apply_template(self):
        template_file = os.path.join(self.temp_dir, "my_template.yaml")
        template_data = {
            "required_prefix_len": 24,
            "reservations": [{"id": "hosts", "cidr_offset": "0.0.0.16/28", "allocatable": True}],
        }
        with open(template_file, "w") as f:
            yaml.dump(template_data, f)

        env = Environment()
        from src.net_mgmt.jinja import register_filters

        register_filters(env)

        net = Network(name="my_net", cidr="10.0.1.0/24")
        template = env.from_string("{{ (net | apply_reservation_template(tmpl)).applied | join(',') }}")
        rendered = template.render(net=net, tmpl=template_file)
        self.assertEqual(rendered, "hosts")
        self.assertEqual(net.reservations[0].cidr, "10.0.1.16/28")


if __name__ == "__main__":
    unittest.main()
