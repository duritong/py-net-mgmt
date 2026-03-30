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


if __name__ == "__main__":
    unittest.main()
