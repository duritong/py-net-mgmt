import os
import unittest

import yaml

from src.net_mgmt.loader import (
    format_yaml_node,
    get_yaml_handler,
    load_all_networks,
    load_network_from_file,
    save_network_to_file,
)


class TestLoader(unittest.TestCase):
    def setUp(self):
        os.makedirs(os.path.join("networks_test", "networks"), exist_ok=True)
        self.test_file = os.path.join("networks_test", "networks", "test_net.yaml")
        with open(self.test_file, "w") as f:
            yaml.dump(
                {
                    "cidr": "192.168.1.0/24",
                    "vlan": 100,
                    "description": "Test Network",
                    "reservations": [{"id": "res-10", "cidr": "192.168.1.10/32", "comment": "Test"}],
                },
                f,
            )

    def tearDown(self):
        os.remove(self.test_file)
        os.rmdir(os.path.join("networks_test", "networks"))
        os.rmdir("networks_test")

    def test_load_network_from_file(self):
        net = load_network_from_file(self.test_file)
        self.assertEqual(net.name, "test_net")
        self.assertEqual(str(net.cidr), "192.168.1.0/24")
        self.assertEqual(net.vlan, 100)
        self.assertEqual(len(net.reservations), 1)
        self.assertEqual(net.reservations[0].id, "res-10")
        self.assertEqual(str(net.reservations[0].cidr), "192.168.1.10/32")

    def test_load_all_networks(self):
        nets = load_all_networks("networks_test")
        self.assertEqual(len(nets), 1)
        self.assertEqual(nets[0].name, "test_net")

    def test_reservations_with_same_id_preserved_after_formatting_and_validation(self):
        # Create a network file with 2 reservations having the same id but from different subranges
        same_id_file = os.path.join("networks_test", "networks", "same_id_net.yaml")
        yaml_content = """cidr: 192.168.1.0/24
description: Same ID reservations test
reservations:
  - id: dhcp # Range 1 comment
    cidr: 192.168.1.10-192.168.1.20
    comment: First subrange
    allocatable: true
  - id: dhcp # Range 2 comment
    cidr: 192.168.1.30-192.168.1.40
    comment: Second subrange
    allocatable: true
"""
        with open(same_id_file, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        try:
            # 1. Load and format using format_yaml_node
            yaml_rt = get_yaml_handler()
            with open(same_id_file, "r", encoding="utf-8") as f:
                data = yaml_rt.load(f)

            formatted = format_yaml_node(data)
            with open(same_id_file, "w", encoding="utf-8") as f:
                yaml_rt.dump(formatted, f)

            # 2. Verify both reservations are preserved and network validates
            net = load_network_from_file(same_id_file)
            net.validate()
            self.assertEqual(len(net.reservations), 2)
            self.assertEqual(net.reservations[0].id, "dhcp")
            self.assertEqual(net.reservations[1].id, "dhcp")
            self.assertEqual(net.reservations[0].cidr, "192.168.1.10-192.168.1.20")
            self.assertEqual(net.reservations[1].cidr, "192.168.1.30-192.168.1.40")

            # 3. Save network back to file using save_network_to_file (which applies formatting)
            save_network_to_file(net)

            with open(same_id_file, "r", encoding="utf-8") as f:
                saved_content = f.read()

            self.assertIn("192.168.1.10-192.168.1.20", saved_content)
            self.assertIn("192.168.1.30-192.168.1.40", saved_content)
            self.assertIn("# Range 1 comment", saved_content)
            self.assertIn("# Range 2 comment", saved_content)
            self.assertEqual(saved_content.count("id: dhcp"), 2)

            # 4. Reload and validate again
            reloaded_net = load_network_from_file(same_id_file)
            reloaded_net.validate()
            self.assertEqual(len(reloaded_net.reservations), 2)
            self.assertEqual(reloaded_net.reservations[0].cidr, "192.168.1.10-192.168.1.20")
            self.assertEqual(reloaded_net.reservations[1].cidr, "192.168.1.30-192.168.1.40")
        finally:
            if os.path.exists(same_id_file):
                os.remove(same_id_file)


if __name__ == "__main__":
    unittest.main()
