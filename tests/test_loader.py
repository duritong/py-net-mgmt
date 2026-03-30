import os
import unittest

import yaml

from src.net_mgmt.loader import load_all_networks, load_network_from_file


class TestLoader(unittest.TestCase):
    def setUp(self):
        os.makedirs("networks_test", exist_ok=True)
        self.test_file = os.path.join("networks_test", "test_net.yaml")
        with open(self.test_file, "w") as f:
            yaml.dump(
                {
                    "cidr": "192.168.1.0/24",
                    "vlan": 100,
                    "bridge_domain": "BD1",
                    "epg": "EPG1",
                    "description": "Test Network",
                    "reservations": [{"id": "res-10", "cidr": "192.168.1.10/32", "comment": "Test"}],
                },
                f,
            )

    def tearDown(self):
        os.remove(self.test_file)
        os.rmdir("networks_test")

    def test_load_network_from_file(self):
        net = load_network_from_file(self.test_file)
        self.assertEqual(net.name, "test_net")
        self.assertEqual(str(net.cidr), "192.168.1.0/24")
        self.assertEqual(net.vlan, 100)
        self.assertEqual(net.bridge_domain, "BD1")
        self.assertEqual(net.epg, "EPG1")
        self.assertEqual(len(net.reservations), 1)
        self.assertEqual(net.reservations[0].id, "res-10")
        self.assertEqual(str(net.reservations[0].cidr), "192.168.1.10/32")

    def test_load_all_networks(self):
        nets = load_all_networks("networks_test")
        self.assertEqual(len(nets), 1)
        self.assertEqual(nets[0].name, "test_net")


if __name__ == "__main__":
    unittest.main()
