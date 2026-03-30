import os
import shutil
import tempfile
import unittest

from net_mgmt.core import Allocation, Network
from net_mgmt.reports import generate_markdown_report


class TestMarkdownReport(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_file = os.path.join(self.test_dir, "report.md")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_markdown_usage_reporting(self):
        net = Network(name="test_net", cidr="192.168.100.0/24")
        net.add_reservation(id="pool1", cidr="192.168.100.10-192.168.100.20", comment="Pool 1", allocatable=True)
        net.allocations.append(Allocation(ip="192.168.100.10", hostname="host1"))

        generate_markdown_report([net], self.output_file)

        with open(self.output_file, "r") as f:
            content = f.read()

        self.assertIn("| Usage |", content)
        self.assertIn("| IP/CIDR |", content)
        self.assertIn("| Hostname/Comment |", content)
        self.assertIn("| Context |", content)
        self.assertIn("| test_net | 192.168.100.0/24 | default |", content)
        self.assertIn("- **Context**: `default`", content)
        # 1/11 = 9.09% -> 9.1%
        self.assertIn("1/11 (9.1%)", content)
        self.assertIn("**Reserve Gateway**: `True`", content)
        self.assertIn("### Unreserved Ranges", content)
        self.assertIn("192.168.100.6/31", content)


if __name__ == "__main__":
    unittest.main()
