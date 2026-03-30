import unittest
from unittest.mock import patch

import jinja2

from src.net_mgmt.core import Allocation, Network
from src.net_mgmt.jinja import network_by_name, networks_in_bridge_domain, register_filters


class TestJinja(unittest.TestCase):
    def setUp(self):
        self.networks = [
            Network(name="net1", cidr="10.0.1.0/24", bridge_domain="BD1", epg="EPG1"),
            Network(name="net2", cidr="10.0.2.0/24", bridge_domain="BD1", epg="EPG2"),
            Network(name="net3", cidr="10.0.3.0/24", bridge_domain="BD2", epg="EPG1"),
        ]

    def test_network_by_name_explicit(self):
        net = network_by_name(self.networks, "net2")
        self.assertIsNotNone(net)
        self.assertEqual(str(net.cidr), "10.0.2.0/24")

        net = network_by_name(self.networks, "net4")
        self.assertIsNone(net)

    @patch("src.net_mgmt.jinja.get_database")
    def test_network_by_name_implicit(self, mock_get_db):
        mock_get_db.return_value = self.networks

        # Test usage: 'net2' | network_by_name
        net = network_by_name("net2")
        self.assertIsNotNone(net)
        self.assertEqual(str(net.cidr), "10.0.2.0/24")
        mock_get_db.assert_called()

    def test_networks_in_bridge_domain_explicit(self):
        nets = networks_in_bridge_domain(self.networks, "BD1")
        self.assertEqual(len(nets), 2)
        self.assertEqual(nets[0].name, "net1")
        self.assertEqual(nets[1].name, "net2")

    @patch("src.net_mgmt.jinja.get_database")
    def test_networks_in_bridge_domain_implicit(self, mock_get_db):
        mock_get_db.return_value = self.networks

        # Test usage: 'BD1' | networks_in_bridge_domain
        nets = networks_in_bridge_domain("BD1")
        self.assertEqual(len(nets), 2)
        mock_get_db.assert_called()


class TestJinjaRendering(unittest.TestCase):
    def setUp(self):
        self.networks = [
            Network(name="net1", cidr="10.0.1.0/24", bridge_domain="BD1", epg="EPG1"),
            Network(name="net2", cidr="10.0.2.0/24", bridge_domain="BD1", epg="EPG2"),
            Network(name="net3", cidr="10.0.3.0/24", bridge_domain="BD2", epg="EPG1"),
        ]
        self.networks[0].allocations.append(Allocation(ip="10.0.1.10", hostname="host1"))
        self.networks[0].allocations.append(Allocation(ip="10.0.1.20", hostname="host2", comment="db server"))
        self.networks[1].allocations.append(Allocation(ip="10.0.2.50", hostname="web1"))

        self.env = jinja2.Environment()
        register_filters(self.env)

    @patch("src.net_mgmt.jinja.get_database")
    def test_network_by_name_filter(self, mock_get_db):
        mock_get_db.return_value = self.networks

        # Test implicit usage (relies on get_database)
        template = self.env.from_string("{{ ('net1' | network_by_name).cidr }}")
        self.assertEqual(template.render(), "10.0.1.0/24")

        # Test explicit usage (passing networks)
        template2 = self.env.from_string("{{ (networks | network_by_name('net2')).cidr }}")
        self.assertEqual(template2.render(networks=self.networks), "10.0.2.0/24")

    @patch("src.net_mgmt.jinja.get_database")
    def test_networks_in_bridge_domain_filter(self, mock_get_db):
        mock_get_db.return_value = self.networks

        # Test implicit usage
        template = self.env.from_string(
            "{% for net in 'BD1' | networks_in_bridge_domain %}{{ net.name }},{% endfor %}"
        )
        self.assertEqual(template.render(), "net1,net2,")

        # Test explicit usage
        template2 = self.env.from_string(
            "{% for net in networks | networks_in_bridge_domain('BD2') %}{{ net.name }}{% endfor %}"
        )
        self.assertEqual(template2.render(networks=self.networks), "net3")

    @patch("src.net_mgmt.jinja.get_database")
    def test_networks_in_epg_filter(self, mock_get_db):
        mock_get_db.return_value = self.networks

        # Test implicit usage
        template = self.env.from_string(
            "{% for net in 'EPG1' | networks_in_epg %}{{ net.name }},{% endfor %}"
        )
        self.assertEqual(template.render(), "net1,net3,")

        # Test explicit usage
        template2 = self.env.from_string(
            "{% for net in networks | networks_in_epg('EPG2') %}{{ net.name }}{% endfor %}"
        )
        self.assertEqual(template2.render(networks=self.networks), "net2")

    def test_query_allocations_filter(self):
        # Test query by hostname
        template = self.env.from_string(
            "{% set allocs = net | query_allocations('host1') %}"
            "{% for a in allocs %}{{ a.hostname }}{% endfor %}"
        )
        self.assertEqual(template.render(net=self.networks[0]), "host1")

        # Test query by partial ip or comment
        template2 = self.env.from_string(
            "{% set allocs = net | query_allocations('db') %}"
            "{% for a in allocs %}{{ a.ip }}{% endfor %}"
        )
        self.assertEqual(template2.render(net=self.networks[0]), "10.0.1.20")

        # Empty result
        template3 = self.env.from_string(
            "{% set allocs = net | query_allocations('notfound') %}"
            "{{ allocs | length }}"
        )
        self.assertEqual(template3.render(net=self.networks[0]), "0")


if __name__ == "__main__":
    unittest.main()
