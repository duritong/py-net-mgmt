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

if __name__ == '__main__':
    unittest.main()
