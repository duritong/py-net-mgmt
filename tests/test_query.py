import unittest

from jinja2 import Environment

from net_mgmt.core import Allocation, Network


class TestQuery(unittest.TestCase):
    def setUp(self):
        self.net = Network(name="test", cidr="10.0.0.0/24")
        self.net.allocations = [
            Allocation(ip="10.0.0.10", hostname="web-server-01"),
            Allocation(ip="10.0.0.11", hostname="web-server-02"),
            Allocation(ip="10.0.0.50", hostname="db-server-01"),
            Allocation(cidr="10.0.0.128/27", comment="k8s-nodes"),
            Allocation(cidr="10.0.0.200-10.0.0.210", comment="dhcp-pool"),
        ]

    def test_query_ip_prefix(self):
        # Starts with 10.0.0.1
        results = self.net.query_allocations("10.0.0.1")
        # Matches 10.0.0.10, 10.0.0.11, and 10.0.0.128/27
        self.assertEqual(len(results), 3)
        names = {a.hostname or a.comment for a in results}
        self.assertIn("web-server-01", names)
        self.assertIn("web-server-02", names)
        self.assertIn("k8s-nodes", names)

    def test_query_hostname_prefix(self):
        results = self.net.query_allocations("web")
        self.assertEqual(len(results), 2)

        results = self.net.query_allocations("db")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "db-server-01")

    def test_query_cidr(self):
        results = self.net.query_allocations("10.0.0.128")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].comment, "k8s-nodes")

    def test_query_range_comment(self):
        results = self.net.query_allocations("dhcp")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].comment, "dhcp-pool")

    def test_jinja_filter(self):
        env = Environment()
        from net_mgmt.jinja import register_filters

        register_filters(env)

        template = env.from_string("{{ net | query_allocations('web') | length }}")
        rendered = template.render(net=self.net)
        self.assertEqual(rendered, "2")

        template = env.from_string("{% for a in net | query_allocations('db') %}{{ a.hostname }}{% endfor %}")
        rendered = template.render(net=self.net)
        self.assertEqual(rendered, "db-server-01")

    def test_query_vlans(self):
        from net_mgmt.core import query_vlans

        # Setup multiple networks with hierarchy
        net1 = Network(name="n1", cidr="10.0.1.0/24", vlan=10, datacenter="DC1", zone="Z1", environment="prod")
        net2 = Network(name="n2", cidr="10.0.2.0/24", vlan=20, datacenter="DC1", zone="Z1", environment="prod")
        net3 = Network(name="n3", cidr="10.0.3.0/24", vlan=30, datacenter="DC1", zone="Z2", environment="prod")
        net4 = Network(name="n4", cidr="10.0.4.0/24", vlan=40, datacenter="DC2", zone="Z1", environment="prod")
        net5 = Network(name="n5", cidr="10.0.5.0/24", vlan=50, datacenter="DC1", zone="Z1", environment="dev")

        nets = [net1, net2, net3, net4, net5]

        # Query all prod vlans in DC1 zone Z1
        self.assertEqual(query_vlans(nets, environment="prod", datacenter="DC1", zone="Z1"), [10, 20])

        # Query all prod vlans in DC1
        self.assertEqual(query_vlans(nets, environment="prod", datacenter="DC1"), [10, 20, 30])

        # Query all dev vlans
        self.assertEqual(query_vlans(nets, environment="dev"), [50])

    def test_hierarchy_inheritance(self):
        import os
        import shutil
        import tempfile

        from net_mgmt.loader import load_all_networks

        test_dir = tempfile.mkdtemp()
        try:
            # Write hierarchy.yaml
            hierarchy_content = """
datacenters:
  DC_Frankfurt:
    timeservers:
      - 10.10.10.1
      - 10.10.10.2
    zones:
      Trusted:
        dns_search:
          - trusted.internal
        bridge_domains:
          BD_Prod:
            environments:
              production:
                epgs:
                  EPG_App:
                    default_mtu: 1500
                    networks:
                      - backend_net
"""
            with open(os.path.join(test_dir, "hierarchy.yaml"), "w") as f:
                f.write(hierarchy_content)

            # Write individual network file with only CIDR
            net_content = """
cidr: 10.0.2.0/24
vlan: 30
"""
            with open(os.path.join(test_dir, "backend_net.yaml"), "w") as f:
                f.write(net_content)

            networks = load_all_networks(test_dir)
            self.assertEqual(len(networks), 1)

            net = networks[0]
            self.assertEqual(net.name, "backend_net")
            # Verify inherited fields
            self.assertEqual(net.datacenter, "DC_Frankfurt")
            self.assertEqual(net.zone, "Trusted")
            self.assertEqual(net.bridge_domain, "BD_Prod")
            self.assertEqual(net.environment, "production")
            self.assertEqual(net.epg, "EPG_App")
            self.assertEqual(net.timeservers, ["10.10.10.1", "10.10.10.2"])
            self.assertEqual(net.dns_search, ["trusted.internal"])
            self.assertEqual(net.default_mtu, 1500)
        finally:
            shutil.rmtree(test_dir)


if __name__ == "__main__":
    unittest.main()
