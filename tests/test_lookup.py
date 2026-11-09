import json
import os
import shutil
import tempfile
import unittest

import jinja2
from click.testing import CliRunner

from net_mgmt import (
    get_network_for_cidr,
    get_network_for_ip,
    lookup,
    register_filters,
    set_db_path,
)
from net_mgmt.cli import cli
from net_mgmt.core import (
    Allocation,
    Network,
    Reservation,
    find_network_for_ip,
    lookup_ip_or_cidr,
)


class TestLookup(unittest.TestCase):
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
            f.write("datacenter: DC_Frankfurt\nzone: DMZ\n")
        with open(os.path.join(self.test_dir, "epgs", "EPG_Web.yaml"), "w") as f:
            f.write("bridge_domain: BD_Web\nenvironment: production\nvlan: 101\n")
        with open(os.path.join(self.test_dir, "datacenters", "DC_Frankfurt.yaml"), "w") as f:
            f.write("timeservers:\n  - 10.10.10.1\n")
        with open(os.path.join(self.test_dir, "zones", "DMZ.yaml"), "w") as f:
            f.write("dns_search:\n  - dmz.corp.local\n")
        with open(os.path.join(self.test_dir, "environments", "production.yaml"), "w") as f:
            f.write("timeservers:\n  - 10.10.10.2\n")

        # Create a sample network file
        self.net_file = os.path.join(self.networks_dir, "corp_web.yaml")
        with open(self.net_file, "w") as f:
            f.write("""
cidr: 10.100.1.0/24
epg: EPG_Web
description: "Corporate Web Tier"
reservations:
  - id: dhcp_pool
    cidr: 10.100.1.50-10.100.1.100
    comment: "DHCP Dynamic Pool"
    allocatable: true
  - id: vip_pool
    cidr: 10.100.1.16/28
    comment: "VIP Pool"
    allocatable: true
  - id: static_infra
    cidr: 10.100.1.10-10.100.1.15
    comment: "Static Infrastructure"
    allocatable: false
allocations:
  - ip: 10.100.1.55
    hostname: web-srv01.corp.local
    comment: "Web Server 01"
  - cidr: 10.100.1.16/28
    comment: "LB Virtual VIPs"
""")

        # Create an aggregate network and child subnet
        self.agg_file = os.path.join(self.networks_dir, "agg_net.yaml")
        with open(self.agg_file, "w") as f:
            f.write("""
cidr: 10.200.0.0/16
aggregate: true
description: "Aggregate Supernet"
""")

        self.sub_file = os.path.join(self.networks_dir, "sub_net.yaml")
        with open(self.sub_file, "w") as f:
            f.write("""
cidr: 10.200.10.0/24
vlan: 210
description: "Child Subnet in Aggregate"
reservations:
  - id: sub_pool
    cidr: 10.200.10.50-10.200.10.100
    comment: "Subnet Pool"
    allocatable: true
allocations:
  - ip: 10.200.10.55
    hostname: agg-child-host.corp.local
""")

        # Create another network in a distinct context
        self.dmz_file = os.path.join(self.networks_dir, "dmz_isolated.yaml")
        with open(self.dmz_file, "w") as f:
            f.write("""
cidr: 10.100.1.0/24
context: isolated_dmz
routable: false
description: "Overlapping CIDR in Isolated Context"
reservations:
  - id: dmz_pool
    cidr: 10.100.1.50-10.100.1.100
    comment: "DMZ Pool"
    allocatable: true
allocations:
  - ip: 10.100.1.55
    hostname: isolated-host.dmz.local
""")

        set_db_path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_core_get_ip_info_single_allocation(self):
        net = Network(
            name="test_net",
            cidr="10.100.1.0/24",
            reservations=[Reservation(id="pool", cidr="10.100.1.50-10.100.1.100", comment="Pool", allocatable=True)],
            allocations=[Allocation(ip="10.100.1.55", hostname="host1", comment="Web Host")],
        )
        info = net.get_ip_info("10.100.1.55")
        self.assertIsNotNone(info)
        self.assertEqual(info["status"], "allocated")
        self.assertEqual(info["ip"], "10.100.1.55")
        self.assertEqual(info["network"], "test_net")
        self.assertEqual(info["allocation"]["hostname"], "host1")
        self.assertEqual(info["allocation"]["type"], "single")
        self.assertEqual(info["reservation"]["id"], "pool")

    def test_core_get_ip_info_subnet_allocation(self):
        net = Network(
            name="test_net",
            cidr="10.100.1.0/24",
            allocations=[Allocation(cidr="10.100.1.16/28", comment="VIPs")],
        )
        info = net.get_ip_info("10.100.1.20")
        self.assertIsNotNone(info)
        self.assertEqual(info["status"], "allocated")
        self.assertEqual(info["allocation"]["type"], "subnet")
        self.assertEqual(info["allocation"]["comment"], "VIPs")

    def test_core_get_ip_info_available_and_reserved(self):
        net = Network(
            name="test_net",
            cidr="10.100.1.0/24",
            reservations=[
                Reservation(id="pool", cidr="10.100.1.50-10.100.1.100", comment="Pool", allocatable=True),
                Reservation(id="static", cidr="10.100.1.10-10.100.1.20", comment="Static", allocatable=False),
            ],
        )
        # IP in allocatable pool but not allocated -> available
        info_avail = net.get_ip_info("10.100.1.60")
        self.assertEqual(info_avail["status"], "available")
        self.assertIsNone(info_avail["allocation"])
        self.assertEqual(info_avail["reservation"]["id"], "pool")

        # IP in non-allocatable reservation -> reserved
        info_res = net.get_ip_info("10.100.1.15")
        self.assertEqual(info_res["status"], "reserved")
        self.assertEqual(info_res["reservation"]["id"], "static")

        # System gateway reservation -> reserved
        info_gw = net.get_ip_info("10.100.1.1")
        self.assertEqual(info_gw["status"], "reserved")
        self.assertEqual(info_gw["reservation"]["id"], "sys-gateway")

        # Unreserved IP
        info_free = net.get_ip_info("10.100.1.8")
        self.assertEqual(info_free["status"], "unreserved")
        self.assertIsNone(info_free["reservation"])
        self.assertIsNone(info_free["allocation"])

        # IP outside network -> None
        self.assertIsNone(net.get_ip_info("192.168.1.1"))

    def test_core_get_cidr_info(self):
        net = Network(
            name="test_net",
            cidr="10.100.1.0/24",
            reservations=[Reservation(id="pool", cidr="10.100.1.50-10.100.1.100", comment="Pool", allocatable=True)],
            allocations=[Allocation(ip="10.100.1.55", hostname="host1", comment="Host 1")],
        )
        # Subnet inside network
        info = net.get_cidr_info("10.100.1.48/28")
        self.assertIsNotNone(info)
        self.assertFalse(info["is_exact_network"])
        self.assertEqual(info["num_addresses"], 16)
        self.assertEqual(len(info["reservations"]), 1)
        self.assertEqual(len(info["allocations"]), 1)
        self.assertEqual(info["allocations"][0]["hostname"], "host1")

        # Exact network CIDR
        info_exact = net.get_cidr_info("10.100.1.0/24")
        self.assertIsNotNone(info_exact)
        self.assertTrue(info_exact["is_exact_network"])

        # CIDR not in network
        self.assertIsNone(net.get_cidr_info("10.200.0.0/16"))

    def test_core_find_network_for_ip_longest_prefix(self):
        agg = Network(name="agg", cidr="10.0.0.0/16", aggregate=True)
        sub = Network(name="sub", cidr="10.0.1.0/24")
        networks = [agg, sub]

        # IP in child subnet matches child subnet
        match = find_network_for_ip("10.0.1.50", networks)
        self.assertEqual(match.name, "sub")

        # IP in aggregate but not in child subnet matches aggregate
        match2 = find_network_for_ip("10.0.2.50", networks)
        self.assertEqual(match2.name, "agg")

        # IP outside all networks returns None
        self.assertIsNone(find_network_for_ip("192.168.1.1", networks))

    def test_core_lookup_ip_or_cidr(self):
        agg = Network(name="agg", cidr="10.200.0.0/16", aggregate=True)
        sub = Network(name="sub", cidr="10.200.10.0/24")
        net = Network(name="corp", cidr="10.100.1.0/24", context="default")
        net_dmz = Network(name="dmz", cidr="10.100.1.0/24", context="dmz")
        networks = [agg, sub, net, net_dmz]

        # 1. IP lookup with multiple contexts
        res_ip = lookup_ip_or_cidr("10.100.1.5", networks)
        self.assertEqual(res_ip["target_type"], "ip")
        self.assertEqual(len(res_ip["matches"]), 2)

        # IP lookup filtered by context
        res_ip_ctx = lookup_ip_or_cidr("10.100.1.5", networks, context="dmz")
        self.assertEqual(len(res_ip_ctx["matches"]), 1)
        self.assertEqual(res_ip_ctx["matches"][0]["context"], "dmz")

        # 2. CIDR exact match
        res_cidr_exact = lookup_ip_or_cidr("10.200.10.0/24", networks)
        self.assertEqual(res_cidr_exact["target_type"], "cidr")
        self.assertEqual(res_cidr_exact["match_type"], "exact")
        self.assertEqual(res_cidr_exact["matches"][0]["network"], "sub")
        self.assertEqual(res_cidr_exact["matches"][0]["parent_aggregate"], "agg (10.200.0.0/16)")

        # 3. CIDR subnet match
        res_cidr_sub = lookup_ip_or_cidr("10.200.10.64/26", networks)
        self.assertEqual(res_cidr_sub["target_type"], "cidr")
        self.assertEqual(res_cidr_sub["match_type"], "subnet")
        self.assertEqual(res_cidr_sub["matches"][0]["network"], "sub")

        # 4. CIDR supernet match
        res_super = lookup_ip_or_cidr("10.0.0.0/8", networks)
        self.assertEqual(res_super["target_type"], "cidr")
        self.assertEqual(res_super["match_type"], "supernet")
        self.assertGreaterEqual(len(res_super["contained_networks"]), 3)

        # 5. Invalid string raises ValueError
        with self.assertRaises(ValueError):
            lookup_ip_or_cidr("invalid_ip_or_cidr", networks)

    def test_cli_lookup_ip_allocated(self):
        result = self.runner.invoke(cli, ["lookup", "10.100.1.55", "--path", self.test_dir])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Target: 10.100.1.55 (IP Address)", result.output)
        self.assertIn("Network: corp_web (10.100.1.0/24)", result.output)
        self.assertIn("Allocated", result.output)
        self.assertIn("web-srv01.corp.local", result.output)
        self.assertIn("Web Server 01", result.output)
        self.assertIn("VLAN: 101", result.output)
        self.assertIn("Bridge Domain: BD_Web", result.output)
        self.assertIn("Environment: production", result.output)
        self.assertIn("EPG: EPG_Web", result.output)
        self.assertIn("Zone: DMZ", result.output)
        self.assertIn("Datacenter: DC_Frankfurt", result.output)

    def test_cli_lookup_ip_in_range_allocation(self):
        result = self.runner.invoke(cli, ["lookup", "10.100.1.20", "--path", self.test_dir])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Allocated", result.output)
        self.assertIn("LB Virtual VIPs", result.output)
        self.assertIn("Subnet/Range (10.100.1.16/28)", result.output)

    def test_cli_lookup_ip_available_and_reserved(self):
        # Available in pool
        result_avail = self.runner.invoke(cli, ["lookup", "10.100.1.60", "--path", self.test_dir])
        self.assertEqual(result_avail.exit_code, 0)
        self.assertIn("Available", result_avail.output)
        self.assertIn("ID: dhcp_pool", result_avail.output)

        # Reserved in static reservation
        result_res = self.runner.invoke(cli, ["lookup", "10.100.1.12", "--path", self.test_dir])
        self.assertEqual(result_res.exit_code, 0)
        self.assertIn("Reserved", result_res.output)
        self.assertIn("ID: static_infra", result_res.output)

        # Reserved gateway
        result_gw = self.runner.invoke(cli, ["lookup", "10.100.1.1", "--path", self.test_dir])
        self.assertEqual(result_gw.exit_code, 0)
        self.assertIn("Reserved", result_gw.output)
        self.assertIn("ID: sys-gateway", result_gw.output)

        # Unreserved
        result_free = self.runner.invoke(cli, ["lookup", "10.100.1.8", "--path", self.test_dir])
        self.assertEqual(result_free.exit_code, 0)
        self.assertIn("Unreserved", result_free.output)

    def test_cli_lookup_cidr(self):
        # Exact match
        result_exact = self.runner.invoke(cli, ["lookup", "10.100.1.0/24", "--path", self.test_dir])
        self.assertEqual(result_exact.exit_code, 0)
        self.assertIn("Exact Network Match", result_exact.output)
        self.assertIn("Network: corp_web (10.100.1.0/24)", result_exact.output)
        self.assertIn("Reservations:", result_exact.output)
        self.assertIn("dhcp_pool", result_exact.output)
        self.assertIn("Allocations:", result_exact.output)
        self.assertIn("web-srv01.corp.local", result_exact.output)

        # Subnet match
        result_sub = self.runner.invoke(cli, ["lookup", "10.100.1.16/28", "--path", self.test_dir])
        self.assertEqual(result_sub.exit_code, 0)
        self.assertIn("Subnet of Network corp_web (10.100.1.0/24)", result_sub.output)
        self.assertIn("Total Addresses: 16", result_sub.output)

        # Supernet match
        result_super = self.runner.invoke(cli, ["lookup", "10.0.0.0/8", "--path", self.test_dir])
        self.assertEqual(result_super.exit_code, 0)
        self.assertIn("CIDR Supernet", result_super.output)
        self.assertIn("Contained Networks:", result_super.output)
        self.assertIn("corp_web", result_super.output)
        self.assertIn("sub_net", result_super.output)

    def test_cli_lookup_formats_json_and_csv(self):
        # JSON IP format
        res_json = self.runner.invoke(cli, ["lookup", "10.100.1.55", "--format", "json", "--path", self.test_dir])
        self.assertEqual(res_json.exit_code, 0)
        data = json.loads(res_json.output)
        self.assertEqual(data["target"], "10.100.1.55")
        self.assertEqual(data["target_type"], "ip")
        self.assertTrue(len(data["matches"]) >= 1)
        self.assertEqual(data["matches"][0]["allocation"]["hostname"], "web-srv01.corp.local")

        # CSV IP format
        res_csv = self.runner.invoke(cli, ["lookup", "10.100.1.55", "--format", "csv", "--path", self.test_dir])
        self.assertEqual(res_csv.exit_code, 0)
        self.assertIn("Target,Type,Network,Network_CIDR,Context,Status", res_csv.output)
        self.assertIn("web-srv01.corp.local", res_csv.output)

        # JSON CIDR format
        res_cidr_json = self.runner.invoke(
            cli, ["lookup", "10.100.1.0/24", "--format", "json", "--path", self.test_dir]
        )
        self.assertEqual(res_cidr_json.exit_code, 0)
        cidr_data = json.loads(res_cidr_json.output)
        self.assertEqual(cidr_data["target_type"], "cidr")
        self.assertEqual(cidr_data["match_type"], "exact")

        # CSV CIDR format
        res_cidr_csv = self.runner.invoke(cli, ["lookup", "10.100.1.0/24", "--format", "csv", "--path", self.test_dir])
        self.assertEqual(res_cidr_csv.exit_code, 0)
        self.assertIn("Target,Type,Match_Type,Network,Network_CIDR", res_cidr_csv.output)

    def test_cli_lookup_context_filtering(self):
        # Without context filter, both corp_web (default context) and dmz_isolated (isolated_dmz) match
        res_all = self.runner.invoke(cli, ["lookup", "10.100.1.55", "--format", "json", "--path", self.test_dir])
        self.assertEqual(res_all.exit_code, 0)
        data_all = json.loads(res_all.output)
        self.assertEqual(len(data_all["matches"]), 2)

        # Filtered to isolated_dmz context
        res_isolated = self.runner.invoke(
            cli, ["lookup", "10.100.1.55", "--context", "isolated_dmz", "--format", "json", "--path", self.test_dir]
        )
        self.assertEqual(res_isolated.exit_code, 0)
        data_isolated = json.loads(res_isolated.output)
        self.assertEqual(len(data_isolated["matches"]), 1)
        self.assertEqual(data_isolated["matches"][0]["context"], "isolated_dmz")
        self.assertEqual(data_isolated["matches"][0]["allocation"]["hostname"], "isolated-host.dmz.local")

    def test_cli_show_ip_and_cidr(self):
        # show ip delegates to lookup
        res_ip = self.runner.invoke(cli, ["show", "ip", "10.100.1.55", "--path", self.test_dir])
        self.assertEqual(res_ip.exit_code, 0)
        self.assertIn("Target: 10.100.1.55 (IP Address)", res_ip.output)
        self.assertIn("web-srv01.corp.local", res_ip.output)

        # show cidr delegates to lookup
        res_cidr = self.runner.invoke(cli, ["show", "cidr", "10.100.1.0/24", "--path", self.test_dir])
        self.assertEqual(res_cidr.exit_code, 0)
        self.assertIn("Exact Network Match", res_cidr.output)

    def test_cli_lookup_errors(self):
        # Target not found
        res_not_found = self.runner.invoke(cli, ["lookup", "192.168.254.10", "--path", self.test_dir])
        self.assertEqual(res_not_found.exit_code, 1)
        self.assertIn("Error: No network found containing IP '192.168.254.10'", res_not_found.output)

        # CIDR not found
        res_cidr_not_found = self.runner.invoke(cli, ["lookup", "192.168.254.0/24", "--path", self.test_dir])
        self.assertEqual(res_cidr_not_found.exit_code, 1)
        self.assertIn("Error: No network found matching CIDR '192.168.254.0/24'", res_cidr_not_found.output)

        # Invalid target format
        res_invalid = self.runner.invoke(cli, ["lookup", "invalid_address", "--path", self.test_dir])
        self.assertEqual(res_invalid.exit_code, 1)
        self.assertIn("neither a valid IP address nor a valid CIDR network", res_invalid.output)

    def test_jinja_filters(self):
        env = jinja2.Environment()
        register_filters(env)

        # 1. network_containing_ip with IP
        tmpl1 = env.from_string("{{ ('10.100.1.55' | network_containing_ip).name }}")
        self.assertEqual(tmpl1.render(), "corp_web")

        # 2. network_containing_ip with CIDR
        tmpl2 = env.from_string("{{ ('10.100.1.16/28' | network_containing_ip).name }}")
        self.assertEqual(tmpl2.render(), "corp_web")

        # 3. network_containing_cidr
        tmpl3 = env.from_string("{{ ('10.100.1.0/24' | network_containing_cidr).name }}")
        self.assertEqual(tmpl3.render(), "corp_web")

        # 4. lookup_target filter
        tmpl4 = env.from_string("{{ ('10.100.1.55' | lookup_target).matches[0].allocation.hostname }}")
        self.assertEqual(tmpl4.render(), "web-srv01.corp.local")

        # 5. ip_info and cidr_info filters on Network object
        tmpl5 = env.from_string(
            "{% set net = '10.100.1.55' | network_containing_ip %}{{ (net | ip_info('10.100.1.55')).status }}"
        )
        self.assertEqual(tmpl5.render(), "allocated")

        tmpl6 = env.from_string(
            "{% set net = '10.100.1.0/24' | network_containing_cidr %}"
            "{{ (net | cidr_info('10.100.1.16/28')).num_addresses }}"
        )
        self.assertEqual(tmpl6.render(), "16")

    def test_programmatic_api(self):
        # lookup helper
        res = lookup("10.100.1.55")
        self.assertEqual(res["target_type"], "ip")
        self.assertGreaterEqual(len(res["matches"]), 1)

        # get_network_for_ip helper
        net_ip = get_network_for_ip("10.100.1.55")
        self.assertIsNotNone(net_ip)
        self.assertEqual(net_ip.name, "corp_web")

        # get_network_for_cidr helper
        net_cidr = get_network_for_cidr("10.100.1.0/24")
        self.assertIsNotNone(net_cidr)
        self.assertEqual(net_cidr.name, "corp_web")

    def test_ipv6_lookup(self):
        v6_net = Network(
            name="v6_net",
            cidr="2001:db8:1::/64",
            reservations=[
                Reservation(id="v6_pool", cidr="2001:db8:1::10-2001:db8:1::20", comment="V6 Pool", allocatable=True)
            ],
            allocations=[Allocation(ip="2001:db8:1::15", hostname="v6-host.corp.local")],
        )
        res_ip = lookup_ip_or_cidr("2001:db8:1::15", [v6_net])
        self.assertEqual(res_ip["target_type"], "ip")
        self.assertEqual(res_ip["matches"][0]["status"], "allocated")
        self.assertEqual(res_ip["matches"][0]["allocation"]["hostname"], "v6-host.corp.local")

        res_net = lookup_ip_or_cidr("2001:db8:1::/64", [v6_net])
        self.assertEqual(res_net["target_type"], "cidr")
        self.assertEqual(res_net["match_type"], "exact")
        self.assertEqual(res_net["matches"][0]["network"], "v6_net")


if __name__ == "__main__":
    unittest.main()
