import os
import shutil
import tempfile
import unittest

import yaml

from src.net_mgmt.loader import is_relational_mode, load_all_networks, save_network_to_file


class TestRelationalDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _setup_relational_db(self, structure):
        """Helper to write a custom relational structure under self.temp_dir"""
        for subdir, files in structure.items():
            os.makedirs(os.path.join(self.temp_dir, subdir), exist_ok=True)
            for filename, content in files.items():
                file_path = os.path.join(self.temp_dir, subdir, f"{filename}.yaml")
                with open(file_path, "w", encoding="utf-8") as f:
                    yaml.dump(content, f)

    def test_relational_mode_detection(self):
        # Empty dir
        self.assertFalse(is_relational_mode(self.temp_dir))

        # Only networks
        os.makedirs(os.path.join(self.temp_dir, "networks"), exist_ok=True)
        self.assertFalse(is_relational_mode(self.temp_dir))

        # Networks + epgs
        os.makedirs(os.path.join(self.temp_dir, "epgs"), exist_ok=True)
        self.assertTrue(is_relational_mode(self.temp_dir))

    def test_successful_relational_load(self):
        db_structure = {
            "datacenters": {
                "DC_Frankfurt": {"timeservers": ["10.10.10.1", "10.10.10.2"], "dns_nameservers": ["8.8.8.8"]}
            },
            "zones": {"Trusted": {"dns_search": ["trusted.internal"]}},
            "environments": {
                "production": {
                    "timeservers": ["10.10.10.3"]  # overrides DC
                }
            },
            "bridge_domains": {"BD_Prod": {"datacenter": "DC_Frankfurt", "zone": "Trusted", "default_mtu": 1500}},
            "epgs": {"EPG_App": {"bridge_domain": "BD_Prod", "environment": "production", "vlan": 30}},
            "networks": {"backend_net": {"cidr": "10.0.1.0/24", "epg": "EPG_App"}},
        }
        self._setup_relational_db(db_structure)

        networks = load_all_networks(self.temp_dir)
        self.assertEqual(len(networks), 1)
        net = networks[0]

        # Verify resolved attributes from relational links
        self.assertEqual(net.name, "backend_net")
        self.assertEqual(str(net.cidr), "10.0.1.0/24")
        self.assertEqual(net.epg, "EPG_App")
        self.assertEqual(net.vlan, 30)
        self.assertEqual(net.bridge_domain, "BD_Prod")
        self.assertEqual(net.environment, "production")
        self.assertEqual(net.datacenter, "DC_Frankfurt")
        self.assertEqual(net.zone, "Trusted")

        # Verify metadata resolution cascade
        # timeservers should resolve from Environment (production) -> 10.10.10.3
        self.assertEqual(net.timeservers, ["10.10.10.3"])
        # dns_nameservers from Datacenter
        self.assertEqual(net.dns_nameservers, ["8.8.8.8"])
        # dns_search from Zone
        self.assertEqual(net.dns_search, ["trusted.internal"])
        # default_mtu from BridgeDomain
        self.assertEqual(net.default_mtu, 1500)

    def test_local_overrides_cascade(self):
        db_structure = {
            "datacenters": {
                "DC_Frankfurt": {
                    "timeservers": ["10.10.10.1"],
                }
            },
            "zones": {"Trusted": {}},
            "environments": {"production": {}},
            "bridge_domains": {"BD_Prod": {"datacenter": "DC_Frankfurt", "zone": "Trusted"}},
            "epgs": {"EPG_App": {"bridge_domain": "BD_Prod", "environment": "production"}},
            "networks": {
                "backend_net": {
                    "cidr": "10.0.1.0/24",
                    "epg": "EPG_App",
                    "timeservers": ["1.1.1.1"],  # Local override
                }
            },
        }
        self._setup_relational_db(db_structure)
        networks = load_all_networks(self.temp_dir)
        net = networks[0]
        self.assertEqual(net.timeservers, ["1.1.1.1"])

    def test_foreign_key_integrity_failure(self):
        db_structure = {
            "datacenters": {},
            "zones": {},
            "environments": {},
            "bridge_domains": {},
            "epgs": {},
            "networks": {"backend_net": {"cidr": "10.0.1.0/24", "epg": "NonExistentEPG"}},
        }
        self._setup_relational_db(db_structure)
        with self.assertRaises(ValueError) as context:
            load_all_networks(self.temp_dir)
        self.assertIn("ForeignKey Integrity", str(context.exception))

    def test_vlan_mismatch_validation_failure(self):
        db_structure = {
            "datacenters": {"DC1": {}},
            "zones": {"Zone1": {}},
            "environments": {"Env1": {}},
            "bridge_domains": {"BD1": {"datacenter": "DC1", "zone": "Zone1"}},
            "epgs": {"EPG1": {"bridge_domain": "BD1", "environment": "Env1", "vlan": 30}},
            "networks": {
                "backend_net": {
                    "cidr": "10.0.1.0/24",
                    "epg": "EPG1",
                    "vlan": 40,  # Mismatch! EPG has 30
                }
            },
        }
        self._setup_relational_db(db_structure)
        with self.assertRaises(ValueError) as context:
            load_all_networks(self.temp_dir)
        self.assertIn("VLAN Match check", str(context.exception))

    def test_bridge_domain_without_epg_failure(self):
        db_structure = {
            "datacenters": {"DC1": {}},
            "zones": {"Zone1": {}},
            "environments": {},
            "bridge_domains": {"BD1": {"datacenter": "DC1", "zone": "Zone1"}},
            "epgs": {},
            "networks": {
                "backend_net": {
                    "cidr": "10.0.1.0/24",
                    "bridge_domain": "BD1",  # Error: BD defined but EPG is missing!
                }
            },
        }
        self._setup_relational_db(db_structure)
        with self.assertRaises(ValueError) as context:
            load_all_networks(self.temp_dir)
        self.assertIn("defines a bridge_domain", str(context.exception))

    def test_environment_mismatch_failure(self):
        db_structure = {
            "datacenters": {"DC1": {}},
            "zones": {"Zone1": {}},
            "environments": {"Env1": {}, "Env2": {}},
            "bridge_domains": {"BD1": {"datacenter": "DC1", "zone": "Zone1"}},
            "epgs": {"EPG1": {"bridge_domain": "BD1", "environment": "Env1"}},
            "networks": {
                "backend_net": {
                    "cidr": "10.0.1.0/24",
                    "epg": "EPG1",
                    "environment": "Env2",  # Mismatch! EPG has Env1
                }
            },
        }
        self._setup_relational_db(db_structure)
        with self.assertRaises(ValueError) as context:
            load_all_networks(self.temp_dir)
        self.assertIn("Environment Match check", str(context.exception))

    def test_datacenter_mismatch_failure(self):
        db_structure = {
            "datacenters": {"DC1": {}, "DC2": {}},
            "zones": {"Zone1": {}},
            "environments": {"Env1": {}},
            "bridge_domains": {"BD1": {"datacenter": "DC1", "zone": "Zone1"}},
            "epgs": {"EPG1": {"bridge_domain": "BD1", "environment": "Env1"}},
            "networks": {
                "backend_net": {
                    "cidr": "10.0.1.0/24",
                    "epg": "EPG1",
                    "datacenter": "DC2",  # Mismatch! Bridge Domain has DC1
                }
            },
        }
        self._setup_relational_db(db_structure)
        with self.assertRaises(ValueError) as context:
            load_all_networks(self.temp_dir)
        self.assertIn("Datacenter Match check", str(context.exception))

    def test_relational_saving_and_pruning(self):
        db_structure = {
            "datacenters": {"DC1": {}},
            "zones": {"Zone1": {}},
            "environments": {"Env1": {}},
            "bridge_domains": {"BD1": {"datacenter": "DC1", "zone": "Zone1"}},
            "epgs": {"EPG1": {"bridge_domain": "BD1", "environment": "Env1", "vlan": 30}},
            "networks": {"backend_net": {"cidr": "10.0.1.0/24", "epg": "EPG1"}},
        }
        self._setup_relational_db(db_structure)

        networks = load_all_networks(self.temp_dir)
        net = networks[0]
        self.assertEqual(net.vlan, 30)

        # Trigger save
        save_network_to_file(net)

        # Read file directly to verify inherited attributes (like vlan) were NOT serialized
        net_file = os.path.join(self.temp_dir, "networks", "backend_net.yaml")
        with open(net_file, "r") as f:
            data = yaml.safe_load(f)

        self.assertNotIn("vlan", data)
        self.assertNotIn("bridge_domain", data)
        self.assertNotIn("environment", data)
        self.assertNotIn("datacenter", data)
        self.assertNotIn("zone", data)
        self.assertEqual(data["epg"], "EPG1")


if __name__ == "__main__":
    unittest.main()
