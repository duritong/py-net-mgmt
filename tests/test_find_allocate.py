import os
import unittest

from src.net_mgmt.core import Network


class TestFindOrAllocate(unittest.TestCase):
    def setUp(self):
        self.network = Network(name="test", cidr="10.0.0.0/24")
        self.network.add_reservation(id="pool1", cidr="10.0.0.10-10.0.0.20", comment="First Pool", allocatable=True)
        self.network.add_reservation(id="pool2", cidr="10.0.0.30-10.0.0.40", comment="Second Pool", allocatable=True)
        self.network.add_reservation(id="pool3", cidr="10.0.0.50-10.0.0.51", comment="Small Pool", allocatable=True)

    def test_find_or_allocate_hostname(self):
        # Should allocate next free IP
        alloc1 = self.network.find_or_allocate_hostname("host1")
        self.assertEqual(alloc1.hostname, "host1")
        self.assertEqual(str(alloc1.ip), "10.0.0.10")

        # Should return existing IP
        alloc2 = self.network.find_or_allocate_hostname("host1")
        self.assertEqual(alloc1, alloc2)

        # Allocate another
        alloc3 = self.network.find_or_allocate_hostname("host2")
        self.assertEqual(str(alloc3.ip), "10.0.0.11")

    def test_find_or_allocate_range_new(self):
        allocs = self.network.find_or_allocate_range("web-nodes", 3)
        self.assertEqual(len(allocs), 1)  # one Allocation object covering a range
        self.assertEqual(allocs[0].cidr, "10.0.0.10-10.0.0.12")
        self.assertEqual(allocs[0].comment, "web-nodes")

    def test_find_or_allocate_range_existing(self):
        # Pre-allocate
        self.network.find_or_allocate_range("db-nodes", 2)

        # Should return the same
        allocs = self.network.find_or_allocate_range("db-nodes", 2)
        self.assertEqual(allocs[0].cidr, "10.0.0.10-10.0.0.11")

        # Expand the range
        allocs2 = self.network.find_or_allocate_range("db-nodes", 4)
        # Should now return list of length 2 or 1 if merged (our code doesn't merge existing, it appends)
        self.assertEqual(len(allocs2), 2)
        self.assertEqual(allocs2[0].cidr, "10.0.0.10-10.0.0.11")
        self.assertEqual(allocs2[1].cidr, "10.0.0.12-10.0.0.13")

    def test_find_or_allocate_range_too_many(self):
        self.network.find_or_allocate_range("nodes", 3)
        with self.assertRaises(ValueError):
            self.network.find_or_allocate_range("nodes", 2)

    def test_find_or_allocate_range_split(self):
        # We need 4 IPs, but pools are fragmented or block is missing
        # pool1 is 10-20 (11 IPs)
        # pool2 is 30-40 (11 IPs)
        # pool3 is 50-51 (2 IPs)
        # Let's allocate 10-18, leaving 2 IPs in pool1
        self.network.find_or_allocate_range("fill", 9)
        # Let's allocate all of pool2
        self.network.find_or_allocate_range("fill2", 11)

        # Request 4 IPs. It should take the 2 remaining from pool1, and 2 from pool3
        allocs = self.network.find_or_allocate_range("split", 4)
        self.assertEqual(len(allocs), 2)
        self.assertEqual(allocs[0].cidr, "10.0.0.19-10.0.0.20")
        self.assertEqual(allocs[1].cidr, "10.0.0.50-10.0.0.51")

    def test_find_or_allocate_range_no_space(self):
        with self.assertRaises(ValueError):
            self.network.find_or_allocate_range("huge", 100)

    def test_delete_allocation(self):
        self.network.find_or_allocate_hostname("host1")
        self.network.find_or_allocate_hostname("host2")

        self.assertEqual(len(self.network.allocations), 2)

        count = self.network.delete_allocations(hostname="host1")
        self.assertEqual(count, 1)
        self.assertEqual(len(self.network.allocations), 1)
        self.assertEqual(self.network.allocations[0].hostname, "host2")

        count = self.network.delete_allocations(hostname="notfound")
        self.assertEqual(count, 0)

    def test_find_or_allocate_with_existing_cidr_allocation(self):
        # Create a network 10.0.0.0/22 (like the user's setup)
        from src.net_mgmt.core import Allocation

        net = Network(name="net1", cidr="10.0.0.0/22")
        net.add_reservation(id="hosts", cidr="10.0.3.0/24", comment="hosts", allocatable=True)

        # Pre-allocate 10.0.3.0 as a CIDR/range allocation
        net.allocations.append(Allocation(cidr="10.0.3.0", comment="foo"))

        # Now find_or_allocate_hostname on hosts pool
        alloc = net.find_or_allocate_hostname("other-host", "hosts")

        # It should correctly skip 10.0.3.0 (which is allocated under cidr) and allocate 10.0.3.1!
        self.assertEqual(str(alloc.ip), "10.0.3.1")
        self.assertEqual(alloc.hostname, "other-host")

    def test_find_or_allocate_persists_standard_yaml_formatting_and_indented_lists(self):
        import shutil
        import tempfile

        from src.net_mgmt.loader import load_network_from_file

        test_dir = tempfile.mkdtemp()
        try:
            networks_dir = os.path.join(test_dir, "networks")
            os.makedirs(networks_dir)
            net_file = os.path.join(networks_dir, "app_net.yaml")
            with open(net_file, "w", encoding="utf-8") as f:
                f.write(
                    "# App Network Header\n"
                    "cidr: 10.0.0.0/24\n"
                    "description: Test app network\n"
                    "# Reservation section\n"
                    "reservations:\n"
                    "  - id: pool1\n"
                    "    cidr: 10.0.0.0/28\n"
                    "    allocatable: true\n"
                )

            net = load_network_from_file(net_file)
            net.find_or_allocate_hostname("web01.internal")
            net.find_or_allocate_range("db-cluster", 2)

            with open(net_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Verify list elements have 2-space indentation under reservations and allocations
            self.assertIn("reservations:\n  - id: pool1", content)
            self.assertIn("allocations:\n  - ip: 10.0.0.7\n    hostname: web01.internal", content)
            self.assertIn("  - cidr: 10.0.0.8-10.0.0.9\n    comment: db-cluster", content)

            # Verify comments preserved
            self.assertIn("# App Network Header", content)
            self.assertIn("# Reservation section", content)

            # Verify key ordering: cidr -> description -> reservations -> allocations
            lines = content.splitlines()
            cidr_idx = next(i for i, line in enumerate(lines) if "cidr: 10.0.0.0/24" in line)
            desc_idx = next(i for i, line in enumerate(lines) if "description: Test app network" in line)
            res_idx = next(i for i, line in enumerate(lines) if "reservations:" in line)
            alloc_idx = next(i for i, line in enumerate(lines) if "allocations:" in line)
            self.assertTrue(cidr_idx < desc_idx < res_idx < alloc_idx)
            # Verify format idempotency: running net-mgmt format should skip because it is already formatted!
            from click.testing import CliRunner

            from src.net_mgmt.cli import cli

            runner = CliRunner()
            fmt_result = runner.invoke(cli, ["format", "--path", networks_dir])
            self.assertEqual(fmt_result.exit_code, 0)
            self.assertIn("Formatted: 0 file(s)", fmt_result.output)
            self.assertIn("Skipped: 1 file(s)", fmt_result.output)
        finally:
            shutil.rmtree(test_dir)

    def test_find_or_allocate_preserves_inline_item_comments(self):
        import shutil
        import tempfile

        from src.net_mgmt.loader import load_network_from_file

        test_dir = tempfile.mkdtemp()
        try:
            networks_dir = os.path.join(test_dir, "networks")
            os.makedirs(networks_dir)
            net_file = os.path.join(networks_dir, "app_net.yaml")
            with open(net_file, "w", encoding="utf-8") as f:
                f.write(
                    "cidr: 10.0.0.0/24\n"
                    "reservations:\n"
                    "  - id: pool1 # Pool 1 inline comment\n"
                    "    cidr: 10.0.0.0/28\n"
                    "    allocatable: true\n"
                    "allocations:\n"
                    "  - ip: 10.0.0.7 # First host comment\n"
                    "    hostname: existing-host\n"
                )

            net = load_network_from_file(net_file)
            net.find_or_allocate_hostname("new-host")

            with open(net_file, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("# Pool 1 inline comment", content)
            self.assertIn("# First host comment", content)
            self.assertIn("hostname: new-host", content)
        finally:
            shutil.rmtree(test_dir)


if __name__ == "__main__":
    unittest.main()
