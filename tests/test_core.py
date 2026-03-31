import unittest

from src.net_mgmt.core import Allocation, Network, Reservation, validate_network_list


class TestOrdering(unittest.TestCase):
    def test_reservation_ordering(self):
        net = Network(name="order_test", cidr="10.0.0.0/24")
        # Add out of order
        net.add_reservation(id="p2", cidr="10.0.0.20/32", comment="p2")
        net.add_reservation(id="p1", cidr="10.0.0.10/32", comment="p1")

        eff_res = net.effective_reservations
        # Sort them as CLI would
        sorted_res = sorted(eff_res, key=lambda r: r.networks[0].network_address)

        # Expectation: sys-network (.0), sys-gateway (.1), sys-internal (.2-5), p1 (.10), p2 (.20), sys-broadcast (.255)
        ids = [r.id for r in sorted_res]
        self.assertEqual(ids, ["sys-network", "sys-gateway", "sys-internal", "p1", "p2", "sys-broadcast"])


class TestNetwork(unittest.TestCase):
    def setUp(self):
        # Basic network 10.0.0.0/24
        # Gateway: 10.0.0.1 (System)
        # Internal: 10.0.0.2-5 (System)
        self.net = Network(name="test", cidr="10.0.0.0/24")

    def test_static_routes(self):
        # Valid static route
        net = Network(
            name="test", cidr="10.0.0.0/24", static_routes=[{"cidr": "192.168.1.0/24", "gateway": "10.0.0.1"}]
        )
        self.assertEqual(len(net.static_routes), 1)
        self.assertEqual(net.static_routes[0].gateway, "10.0.0.1")

        # Optional gateway static route (default to network address + 1)
        net_optional = Network(name="test_optional", cidr="10.0.0.0/24", static_routes=[{"cidr": "192.168.2.0/24"}])
        self.assertEqual(len(net_optional.static_routes), 1)
        self.assertEqual(net_optional.static_routes[0].gateway, "10.0.0.1")

        # Invalid static route
        with self.assertRaisesRegex(ValueError, "Static route gateway 192.168.1.1 is not within network 10.0.0.0/24"):
            Network(
                name="test", cidr="10.0.0.0/24", static_routes=[{"cidr": "192.168.1.0/24", "gateway": "192.168.1.1"}]
            )

    def test_system_reservations(self):
        eff_res = self.net.effective_reservations
        ids = [r.id for r in eff_res]
        self.assertIn("sys-network", ids)
        self.assertIn("sys-gateway", ids)
        self.assertIn("sys-internal", ids)
        self.assertIn("sys-broadcast", ids)

        net_res = next(r for r in eff_res if r.id == "sys-network")
        self.assertEqual(str(net_res.cidr), "10.0.0.0")

        br_res = next(r for r in eff_res if r.id == "sys-broadcast")
        self.assertEqual(str(br_res.cidr), "10.0.0.255")

    def test_no_allocatable_reservations(self):
        with self.assertRaisesRegex(ValueError, "No allocatable reservations found"):
            self.net.get_next_free_ip()

    def test_allocatable_reservation_success(self):
        # Add allocatable pool 10.0.0.10-20
        self.net.add_reservation(id="pool1", cidr="10.0.0.10-10.0.0.20", comment="Pool", allocatable=True)

        ip = self.net.get_next_free_ip()
        self.assertEqual(str(ip), "10.0.0.10")

        # Add allocation for .10
        self.net.allocations.append(Allocation(ip="10.0.0.10", hostname="host1"))

        ip = self.net.get_next_free_ip()
        self.assertEqual(str(ip), "10.0.0.11")

    def test_specific_reservation(self):
        self.net.add_reservation(id="pool1", cidr="10.0.0.10-10.0.0.10", comment="Pool1", allocatable=True)
        self.net.add_reservation(id="pool2", cidr="10.0.0.20-10.0.0.20", comment="Pool2", allocatable=True)

        ip = self.net.get_next_free_ip(reservation_id="pool2")
        self.assertEqual(str(ip), "10.0.0.20")

    def test_reservation_full(self):
        self.net.add_reservation(id="pool1", cidr="10.0.0.10/32", comment="Pool", allocatable=True)
        self.net.allocations.append(Allocation(ip="10.0.0.10", hostname="full"))

        with self.assertRaisesRegex(ValueError, "No free IPs available"):
            self.net.get_next_free_ip()

    def test_system_reservations_blocking(self):
        # Try to create an allocatable reservation that overlaps with gateway (should fail)
        with self.assertRaisesRegex(ValueError, "overlaps"):
            self.net.add_reservation(id="bad_pool", cidr="10.0.0.0/24", comment="Bad", allocatable=True)

    def test_disable_system_reservations(self):
        net = Network(name="test", cidr="10.0.0.0/24", reserve_gateway=False, reserve_internal=False)
        eff_res = net.effective_reservations
        # sys-network and sys-broadcast are still there
        self.assertEqual(len(eff_res), 2)
        ids = [r.id for r in eff_res]
        self.assertIn("sys-network", ids)
        self.assertIn("sys-broadcast", ids)

        # Can now reserve entire range except network/broadcast
        net.add_reservation(id="all", cidr="10.0.0.1-10.0.0.254", comment="All", allocatable=True)

        # .0 is network address, .1 is first host
        # iter_ips on 10.0.0.0/24 yields .1 to .254
        ip = net.get_next_free_ip()
        self.assertEqual(str(ip), "10.0.0.1")

    def test_allocation_outside_reservation(self):
        # Manually add invalid allocation
        self.net.allocations.append(Allocation(ip="10.0.0.99", hostname="rogue"))
        with self.assertRaisesRegex(ValueError, "not within any allocatable reservation"):
            self.net.validate()

    def test_multiple_allocatable_reservations(self):
        self.net.add_reservation(id="p1", cidr="10.0.0.10/32", comment="p1", allocatable=True)
        self.net.add_reservation(id="p2", cidr="10.0.0.20/32", comment="p2", allocatable=True)

        # Fill p1
        self.net.allocations.append(Allocation(ip="10.0.0.10", hostname="h1"))

        # Should jump to p2
        ip = self.net.get_next_free_ip()
        self.assertEqual(str(ip), "10.0.0.20")


class TestNetworkValidation(unittest.TestCase):
    def test_overlapping_routable_networks(self):
        nets = [
            Network(name="n1", cidr="10.0.0.0/24", routable=True),
            Network(name="n2", cidr="10.0.0.0/24", routable=True),
        ]
        with self.assertRaises(ValueError):
            validate_network_list(nets)

    def test_overlapping_non_routable_networks(self):
        nets = [
            Network(name="n1", cidr="10.0.0.0/24", routable=False, context="vrf1"),
            Network(name="n2", cidr="10.0.0.0/24", routable=True, context="default"),
        ]
        # Should not raise because they are in different contexts and one is not routable
        validate_network_list(nets)

    def test_overlapping_same_context_networks(self):
        nets = [
            Network(name="n1", cidr="10.0.0.0/24", routable=False, context="vrf1"),
            Network(name="n2", cidr="10.0.0.0/24", routable=False, context="vrf1"),
        ]
        with self.assertRaises(ValueError):
            validate_network_list(nets)

    def test_fragmentation_complex(self):
        net = Network(
            name="frag-net",
            cidr="192.168.1.0/24",
            reservations=[
                Reservation(id="pool1", cidr="192.168.1.100-192.168.1.102", comment="pool", allocatable=True),
                Reservation(id="pool2", cidr="192.168.1.105-192.168.1.107", comment="pool", allocatable=True),
            ],
        )

        # We need to allocate 5 IPs. It should pull from both pools.
        net.find_or_allocate_range(comment="fragmented-alloc", count=5)

        # Now we should have 5 IPs allocated across the two disjoint pools.
        # Check that we have exactly 5 IPs allocated for this comment
        allocs = [a for a in net.allocations if a.comment == "fragmented-alloc"]

        # IPs should be 100, 101, 102, 105, 106
        allocated_ips = []
        for a in allocs:
            for n in a.networks:
                allocated_ips.extend([str(ip) for ip in n])

        self.assertEqual(len(allocated_ips), 5)
        self.assertIn("192.168.1.100", allocated_ips)
        self.assertIn("192.168.1.106", allocated_ips)
        self.assertNotIn("192.168.1.107", allocated_ips)

    def test_overlapping_subnets_routable(self):
        nets = [
            Network(name="n1", cidr="10.0.0.0/16", routable=True),
            Network(name="n2", cidr="10.0.1.0/24", routable=True),
        ]
        with self.assertRaises(ValueError):
            validate_network_list(nets)


if __name__ == "__main__":
    unittest.main()
