import os
import shutil
import tempfile
import time
import unittest

import jinja2
from click.testing import CliRunner

from net_mgmt.cli import cli
from net_mgmt.core import (
    Allocation,
    DatabaseValidationError,
    Network,
    Reservation,
    validate_network_list,
)
from net_mgmt.jinja import register_filters


class TestIPv6Support(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_dir = tempfile.mkdtemp()
        self.networks_dir = os.path.join(self.test_dir, "networks")
        os.makedirs(self.networks_dir)

        os.makedirs(os.path.join(self.test_dir, "bridge_domains"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "epgs"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "datacenters"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "zones"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "environments"), exist_ok=True)

        with open(os.path.join(self.test_dir, "bridge_domains", "BD_Web.yaml"), "w") as f:
            f.write("datacenter: DC1\nzone: DMZ\n")
        with open(os.path.join(self.test_dir, "epgs", "EPG_Web.yaml"), "w") as f:
            f.write("bridge_domain: BD_Web\nenvironment: production\nvlan: 101\n")
        with open(os.path.join(self.test_dir, "datacenters", "DC1.yaml"), "w") as f:
            f.write("timeservers:\n  - 10.10.10.1\n")
        with open(os.path.join(self.test_dir, "zones", "DMZ.yaml"), "w") as f:
            f.write("dns_search:\n  - dmz.corp.local\n")
        with open(os.path.join(self.test_dir, "environments", "production.yaml"), "w") as f:
            f.write("timeservers:\n  - 10.10.10.2\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_mixed_validation_no_type_error(self):
        v4_1 = Network(name="v4_1", cidr="10.0.1.0/24")
        v4_2 = Network(name="v4_2", cidr="10.0.2.0/24")
        v6_1 = Network(name="v6_1", cidr="2001:db8:1::/64")
        v6_2 = Network(name="v6_2", cidr="2001:db8:2::/64")

        # Mixed routable validation must pass cleanly without cross-family TypeError
        validate_network_list([v4_1, v4_2, v6_1, v6_2])

        # Overlapping within same family must still raise DatabaseValidationError
        v4_dup = Network(name="v4_dup", cidr="10.0.1.0/24")
        with self.assertRaises(DatabaseValidationError):
            validate_network_list([v4_1, v4_dup, v6_1])

        v6_dup = Network(name="v6_dup", cidr="2001:db8:1::/64")
        with self.assertRaises(DatabaseValidationError):
            validate_network_list([v4_1, v6_1, v6_dup])

    def test_ipv6_system_reservations(self):
        net6 = Network(name="v6_test", cidr="2001:db8:1::/64")
        res_ids = [r.id for r in net6.effective_reservations]

        self.assertIn("sys-network", res_ids)
        self.assertNotIn("sys-broadcast", res_ids)
        self.assertIn("sys-gateway", res_ids)
        self.assertIn("sys-internal", res_ids)

        gw_res = next(r for r in net6.effective_reservations if r.id == "sys-gateway")
        self.assertEqual(gw_res.cidr, "2001:db8:1::1")

        internal_res = next(r for r in net6.effective_reservations if r.id == "sys-internal")
        self.assertEqual(internal_res.cidr, "2001:db8:1::2-2001:db8:1::6")

        # Disable gateway and internal
        net6_disabled = Network(name="v6_off", cidr="2001:db8:1::/64", reserve_gateway=False, reserve_internal=False)
        off_ids = [r.id for r in net6_disabled.effective_reservations]
        self.assertIn("sys-network", off_ids)
        self.assertNotIn("sys-gateway", off_ids)
        self.assertNotIn("sys-internal", off_ids)

    def test_ipv6_get_subnets_and_aggregate_cross_version(self):
        agg_v4 = Network(name="agg_v4", cidr="10.0.0.0/16", aggregate=True)
        sub_v4 = Network(name="sub_v4", cidr="10.0.1.0/24")
        agg_v6 = Network(name="agg_v6", cidr="2001:db8:1::/48", aggregate=True)
        sub_v6 = Network(name="sub_v6", cidr="2001:db8:1:10::/64")

        all_nets = [agg_v4, sub_v4, agg_v6, sub_v6]

        self.assertEqual([n.name for n in agg_v4.get_subnets(all_nets)], ["sub_v4"])
        self.assertEqual([n.name for n in agg_v6.get_subnets(all_nets)], ["sub_v6"])

        self.assertEqual(sub_v4.get_parent_aggregate(all_nets).name, "agg_v4")
        self.assertEqual(sub_v6.get_parent_aggregate(all_nets).name, "agg_v6")

    def test_ipv6_scale_get_next_free_ip_with_large_subnet_allocation(self):
        net = Network(
            name="v6_scale",
            cidr="2001:db8:1::/64",
            reservations=[
                Reservation(id="pool", cidr="2001:db8:1::/64", comment="pool", allocatable=True),
            ],
            allocations=[
                # /80 allocation has 2^48 addresses; must NOT freeze process
                Allocation(cidr="2001:db8:1:0:1::/80", comment="Large routed subnet"),
            ],
        )

        start = time.time()
        ip = net.get_next_free_ip()
        elapsed = time.time() - start

        # Must return in under 0.1s
        self.assertLess(elapsed, 0.1)
        self.assertIsNotNone(ip)
        self.assertTrue(str(ip).startswith("2001:db8:1::"))

    def test_ipv6_find_or_allocate_range_scale(self):
        net = Network(
            name="v6_range",
            cidr="2001:db8:1::/64",
            reservations=[
                Reservation(id="pool", cidr="2001:db8:1::1000-2001:db8:1::2000", comment="pool", allocatable=True),
            ],
        )

        start = time.time()
        allocs = net.find_or_allocate_range(comment="IPv6 Host Block", count=4)
        elapsed = time.time() - start

        self.assertLess(elapsed, 0.1)
        self.assertEqual(len(allocs), 1)
        self.assertEqual(allocs[0].cidr, "2001:db8:1::1000-2001:db8:1::1003")

    def test_dual_stack_peer_resolution(self):
        v4_net = Network(name="web_v4", cidr="10.100.1.0/24", epg="EPG_Web", vlan=101)
        v6_net = Network(name="web_v6", cidr="2001:db8:1::/64", epg="EPG_Web", vlan=101)
        other_net = Network(name="db_v4", cidr="10.100.2.0/24", epg="EPG_DB", vlan=102)

        all_nets = [v4_net, v6_net, other_net]

        self.assertEqual(v4_net.get_dual_stack_peer(all_nets), v6_net)
        self.assertEqual(v6_net.get_dual_stack_peer(all_nets), v4_net)
        self.assertIsNone(other_net.get_dual_stack_peer(all_nets))

    def test_ipv6_apply_reservation_template(self):
        net = Network(name="v6_template", cidr="2001:db8:1::/64")
        template_data = {
            "required_prefix_len": 64,
            "reservations": [
                {
                    "id": "v6_infra",
                    "cidr_offset": "::10/128",
                    "comment": "Infra Single Host",
                    "allocatable": False,
                },
                {
                    "id": "v6_pool",
                    "cidr_offset": "::100/120",
                    "comment": "DHCPv6 Subnet",
                    "allocatable": True,
                },
            ],
        }

        res = net.apply_reservation_template(template_data)
        self.assertEqual(res["applied"], ["v6_infra", "v6_pool"])
        self.assertEqual(len(net.reservations), 2)

    def test_cli_mixed_networks(self):
        # Create dual-stack networks under self.test_dir
        with open(os.path.join(self.networks_dir, "web_v4.yaml"), "w") as f:
            f.write("cidr: 10.100.1.0/24\nepg: EPG_Web\nvlan: 101\n")
        with open(os.path.join(self.networks_dir, "web_v6.yaml"), "w") as f:
            f.write("cidr: 2001:db8:1::/64\nepg: EPG_Web\nvlan: 101\n")

        # 1. validate
        r_val = self.runner.invoke(cli, ["validate", "--path", self.test_dir])
        self.assertEqual(r_val.exit_code, 0)
        self.assertIn("Successfully validated 2 networks", r_val.output)

        # 2. list networks
        r_list = self.runner.invoke(cli, ["list", "networks", "--path", self.test_dir])
        self.assertEqual(r_list.exit_code, 0)
        self.assertIn("web_v4", r_list.output)
        self.assertIn("web_v6", r_list.output)

        # 3. list networks filtered by IP version
        r_v4 = self.runner.invoke(cli, ["list", "networks", "--ip-version", "4", "--path", self.test_dir])
        self.assertEqual(r_v4.exit_code, 0)
        self.assertIn("web_v4", r_v4.output)
        self.assertNotIn("web_v6", r_v4.output)

        r_v6 = self.runner.invoke(cli, ["list", "networks", "--ip-version", "6", "--path", self.test_dir])
        self.assertEqual(r_v6.exit_code, 0)
        self.assertIn("web_v6", r_v6.output)
        self.assertNotIn("web_v4", r_v6.output)

        # 4. list sorted by cidr
        r_sort = self.runner.invoke(cli, ["list", "networks", "--sort-by", "cidr", "--path", self.test_dir])
        self.assertEqual(r_sort.exit_code, 0)

        # 5. format
        r_fmt = self.runner.invoke(cli, ["format", "--path", self.test_dir])
        self.assertEqual(r_fmt.exit_code, 0)

    def test_jinja_dual_stack_filters(self):
        env = jinja2.Environment()
        register_filters(env)

        v4 = Network(name="app_v4", cidr="10.100.1.0/24", epg="EPG_App", vlan=10)
        v6 = Network(name="app_v6", cidr="2001:db8:1::/64", epg="EPG_App", vlan=10)
        networks = [v4, v6]

        # dual_stack_peer filter
        tmpl_peer = env.from_string("{{ (v4 | dual_stack_peer(networks)).name }}")
        self.assertEqual(tmpl_peer.render(v4=v4, networks=networks), "app_v6")

        tmpl_peer_v6 = env.from_string("{{ (v6 | dual_stack_peer(networks)).name }}")
        self.assertEqual(tmpl_peer_v6.render(v6=v6, networks=networks), "app_v4")

        # networks_by_ip_version filter
        tmpl_v6 = env.from_string("{{ (networks | networks_by_ip_version(6))[0].name }}")
        self.assertEqual(tmpl_v6.render(networks=networks), "app_v6")

        tmpl_v4 = env.from_string("{{ (networks | networks_by_ip_version(4))[0].name }}")
        self.assertEqual(tmpl_v4.render(networks=networks), "app_v4")


if __name__ == "__main__":
    unittest.main()
