import os
import shutil
import tempfile
import unittest

from net_mgmt.core import Allocation, Network
from net_mgmt.reports import generate_markdown_report


class TestMarkdownReport(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "report_dir")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_markdown_usage_reporting(self):
        net = Network(name="test_net", cidr="192.168.100.0/24")
        net.add_reservation(id="pool1", cidr="192.168.100.10-192.168.100.20", comment="Pool 1", allocatable=True)
        net.allocations.append(Allocation(ip="192.168.100.10", hostname="host1"))

        generate_markdown_report([net], self.output_dir)

        readme_path = os.path.join(self.output_dir, "README.md")
        self.assertTrue(os.path.exists(readme_path))

        with open(readme_path, "r") as f:
            readme_content = f.read()

        self.assertIn("| Context |", readme_content)
        self.assertIn("[test_net](networks/test_net.md) | `192.168.100.0/24` | `default` |", readme_content)

        net_path = os.path.join(self.output_dir, "networks", "test_net.md")
        self.assertTrue(os.path.exists(net_path))

        with open(net_path, "r") as f:
            net_content = f.read()

        self.assertIn("| Usage |", net_content)
        self.assertIn("| IP/CIDR |", net_content)
        self.assertIn("| Hostname/Comment |", net_content)
        self.assertIn("- **Context**: `default`", net_content)
        # 1/11 = 9.09% -> 9.1%
        self.assertIn("1/11 (9.1%)", net_content)
        self.assertIn("**Reserve Gateway**: `True`", net_content)
        self.assertIn("## Unreserved Ranges", net_content)
        self.assertIn("192.168.100.6 - 192.168.100.9", net_content)

    def test_markdown_report_sorting(self):
        # Create networks with varying datacenter, zone, bridge_domain, epg, and vlan settings
        net1 = Network(name="net1", cidr="10.0.1.0/24", datacenter="DC2", zone="zoneB", epg="epgA", vlan=10)
        net2 = Network(
            name="net2",
            cidr="10.0.2.0/24",
            datacenter="DC1",
            zone="zoneA",
            bridge_domain="BD_Prod",
            epg="epgA",
            vlan=20,
        )
        net3 = Network(
            name="net3", cidr="10.0.3.0/24", datacenter="DC1", zone="zoneA", bridge_domain="BD_Prod", epg="epgA", vlan=5
        )
        net4 = Network(name="net4", cidr="10.0.4.0/24", datacenter="DC1", zone="zoneB", epg="epgA", vlan=10)
        net5 = Network(name="net5", cidr="10.0.5.0/24", datacenter=None, zone="zoneA", epg="epgA", vlan=10)
        net6 = Network(
            name="net6", cidr="10.0.6.0/24", datacenter="DC1", zone="zoneA", bridge_domain="BD_DMZ", epg="epgA", vlan=12
        )

        generate_markdown_report([net1, net2, net3, net4, net5, net6], self.output_dir)

        readme_path = os.path.join(self.output_dir, "README.md")
        self.assertTrue(os.path.exists(readme_path))

        with open(readme_path, "r") as f:
            readme_content = f.read()

        # Expected sorting order:
        # 1. net6: DC1, zoneA, BD_DMZ, epgA (BD_DMZ sorts alphabetically before BD_Prod)
        # 2. net2: DC1, zoneA, BD_Prod, epgA, name "net2" (net2 sorts alphabetically before net3)
        # 3. net3: DC1, zoneA, BD_Prod, epgA, name "net3"
        # 4. net4: DC1, zoneB, unassigned, epgA
        # 5. net1: DC2, zoneB, unassigned, epgA
        # 6. net5: None, zoneA, unassigned, epgA (None DC sorts last)
        pos6 = readme_content.find("[net6](networks/net6.md)")
        pos3 = readme_content.find("[net3](networks/net3.md)")
        pos2 = readme_content.find("[net2](networks/net2.md)")
        pos4 = readme_content.find("[net4](networks/net4.md)")
        pos1 = readme_content.find("[net1](networks/net1.md)")
        pos5 = readme_content.find("[net5](networks/net5.md)")

        self.assertNotEqual(pos6, -1)
        self.assertNotEqual(pos3, -1)
        self.assertNotEqual(pos2, -1)
        self.assertNotEqual(pos4, -1)
        self.assertNotEqual(pos1, -1)
        self.assertNotEqual(pos5, -1)

        self.assertLess(pos6, pos2)
        self.assertLess(pos2, pos3)
        self.assertLess(pos3, pos4)
        self.assertLess(pos4, pos1)
        self.assertLess(pos1, pos5)

    def test_custom_templates(self):
        templates_dir = os.path.join(self.test_dir, "my_templates")
        os.makedirs(templates_dir)

        with open(os.path.join(templates_dir, "index.md"), "w", encoding="utf-8") as f:
            f.write("# Custom Index\nTotal: {{ tree | length }}")

        net = Network(name="test_net", cidr="192.168.100.0/24")
        generate_markdown_report([net], self.output_dir, templates_dir=templates_dir)

        readme_path = os.path.join(self.output_dir, "README.md")
        self.assertTrue(os.path.exists(readme_path))

        with open(readme_path, "r", encoding="utf-8") as f:
            readme_content = f.read()

        self.assertEqual(readme_content, "# Custom Index\nTotal: 0")


if __name__ == "__main__":
    unittest.main()
