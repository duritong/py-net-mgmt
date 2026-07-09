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
        self.assertIn("| [test_net](test_net.md) | 192.168.100.0/24 | default |", readme_content)

        net_path = os.path.join(self.output_dir, "test_net.md")
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
        self.assertIn("192.168.100.6/31", net_content)


if __name__ == "__main__":
    unittest.main()
