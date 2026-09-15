import unittest

from src.net_mgmt.core import (
    Allocation,
    DatabaseValidationError,
    Network,
    Reservation,
    StaticRoute,
    validate_network_list,
)


class TestOrdering(unittest.TestCase):
    def test_reservation_ordering(self):
        net = Network(name="order_test", cidr="10.0.0.0/24")
        # Add out of order
        net.add_reservation(id="p2", cidr="10.0.0.20/32", comment="p2")
        net.add_reservation(id="p1", cidr="10.0.0.10/32", comment="p1")

        eff_res = net.effective_reservations
        # Sort them as CLI would
        sorted_res = sorted(eff_res, key=lambda r: r.networks[0].network_address)

        # Expectation: sys-network (.0), sys-gateway (.1), sys-internal (.2-6), p1 (.10), p2 (.20), sys-broadcast (.255)
        ids = [r.id for r in sorted_res]
        self.assertEqual(ids, ["sys-network", "sys-gateway", "sys-internal", "p1", "p2", "sys-broadcast"])


class TestNetwork(unittest.TestCase):
    def setUp(self):
        # Basic network 10.0.0.0/24
        # Gateway: 10.0.0.1 (System)
        # Internal: 10.0.0.2-6 (System)
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
        # Creating a pool that overlaps with system reservations is now allowed!
        # It acts as an exclude-rule, so system IPs are skipped automatically.
        self.net.add_reservation(id="large_pool", cidr="10.0.0.0/24", comment="Large Pool", allocatable=True)

        # Free IP should skip .0, .1, and .2-.6, returning .7!
        ip = self.net.get_next_free_ip()
        self.assertEqual(str(ip), "10.0.0.7")

    def test_subnet_broadcast_no_conflict(self):
        # In a 10.0.0.0/22 network, 10.0.3.0/24 includes the broadcast 10.0.3.255.
        # This is now fully allowed without overlaps error!
        net = Network(name="slash-22", cidr="10.0.0.0/22")
        net.add_reservation(id="pool_24", cidr="10.0.3.0/24", comment="Pool 24", allocatable=True)

        # Allocating should work and skip the broadcast address (which is 10.0.3.255)
        ip = net.get_next_free_ip()
        self.assertEqual(str(ip), "10.0.3.0")

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

    def test_unreserved_ranges_no_split(self):
        # Create a network with no gateway or internal system reservations and no user reservations
        import ipaddress

        net = Network(name="global-ovn", cidr="10.3.128.0/18", reserve_gateway=False, reserve_internal=False)
        unreserved = net.get_unreserved_ranges()

        # With sys-network and sys-broadcast skipped, the unreserved range is exactly self.cidr
        self.assertEqual(len(unreserved), 1)
        self.assertEqual(unreserved[0], ipaddress.ip_network("10.3.128.0/18"))

    def test_unreserved_ranges_filter_boundaries(self):
        # Create a network 10.0.0.0/24 with 10.0.0.1 reserved (adjacent to network address)
        # And 10.0.0.254 reserved (adjacent to broadcast address)

        net = Network(name="boundary-net", cidr="10.0.0.0/24", reserve_gateway=False, reserve_internal=False)
        net.add_reservation(id="gw", cidr="10.0.0.1", comment="gw", allocatable=False)
        net.add_reservation(id="last", cidr="10.0.0.254", comment="last", allocatable=False)

        unreserved = net.get_unreserved_ranges()

        # None of the unreserved ranges should be the unusable network address (10.0.0.0/32)
        # or the broadcast address (10.0.0.255/32)
        for r in unreserved:
            self.assertNotEqual(str(r), "10.0.0.0/32")
            self.assertNotEqual(str(r), "10.0.0.255/32")

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

    def test_configurable_internal_reservations(self):
        # Test case 1: Custom reserve_internal_until=5 (matches old default behavior)
        net_until_5 = Network(name="until_5", cidr="10.0.0.0/24", reserve_internal_until=5)
        net_until_5.add_reservation(id="pool", cidr="10.0.0.0/24", comment="Pool", allocatable=True)
        # Should skip .0, .1 (gateway), and .2-.5, returning .6
        self.assertEqual(str(net_until_5.get_next_free_ip()), "10.0.0.6")

        # Test case 2: Custom reserve_internal_until=8
        net_until_8 = Network(name="until_8", cidr="10.0.0.0/24", reserve_internal_until=8)
        net_until_8.add_reservation(id="pool", cidr="10.0.0.0/24", comment="Pool", allocatable=True)
        # Should skip .0, .1 (gateway), and .2-.8, returning .9
        self.assertEqual(str(net_until_8.get_next_free_ip()), "10.0.0.9")

        # Test case 3: Disable reserve_internal completely, even if reserve_internal_until is set
        net_disabled = Network(name="disabled", cidr="10.0.0.0/24", reserve_internal=False, reserve_internal_until=10)
        net_disabled.add_reservation(id="pool", cidr="10.0.0.0/24", comment="Pool", allocatable=True)
        # Should skip .0, .1 (gateway), and return .2
        self.assertEqual(str(net_disabled.get_next_free_ip()), "10.0.0.2")

    def test_batch_validation_reporting(self):
        # 1. Test Network.validate() accumulating multiple errors
        net = Network(name="multi_err", cidr="10.0.0.0/24")
        # Issue 1: Reservation outside of network CIDR
        net.reservations.append(
            Reservation(id="out_of_bounds_res", cidr="192.168.1.0/24", comment="Outside", allocatable=True)
        )
        # Issue 2: Allocation with no allocatable reservation (already exists, but we bypass add_allocation)
        net.allocations.append(Allocation(ip="10.0.0.99", hostname="unreserved"))

        with self.assertRaises(DatabaseValidationError) as ctx:
            net.validate()

        self.assertEqual(len(ctx.exception.errors), 2)
        # Check first error content
        self.assertTrue(any("Reservation 192.168.1.0/24" in err for err in ctx.exception.errors))
        # Check second error content
        self.assertTrue(
            any(
                "Allocation 10.0.0.99 (hostname: 'unreserved') is not within any allocatable reservation" in err
                for err in ctx.exception.errors
            )
        )

        # 2. Test validate_network_list() accumulating multiple overlap errors
        nets = [
            Network(name="n1", cidr="10.0.0.0/16", routable=True),
            Network(name="n2", cidr="10.0.1.0/24", routable=True),
            Network(name="n3", cidr="10.0.2.0/24", routable=True),
        ]
        with self.assertRaises(DatabaseValidationError) as ctx_list:
            validate_network_list(nets)

        # There should be 4 overlap errors (2 from the global routable checks and 2 from context 'default' checks)
        self.assertEqual(len(ctx_list.exception.errors), 4)
        self.assertTrue(any("n1" in err and "n2" in err for err in ctx_list.exception.errors))
        self.assertTrue(any("n1" in err and "n3" in err for err in ctx_list.exception.errors))

        # 3. Test de-duplicated allocation overlaps with descriptive identifiers
        net_overlaps = Network(name="overlaps_test", cidr="10.0.0.0/24")
        net_overlaps.reservations.append(Reservation(id="pool", cidr="10.0.0.0/24", comment="Pool", allocatable=True))
        net_overlaps.allocations.append(Allocation(ip="10.0.0.10", hostname="host-a", comment="A"))
        net_overlaps.allocations.append(Allocation(ip="10.0.0.10", hostname="host-b", comment="B"))

        with self.assertRaises(DatabaseValidationError) as ctx_overlaps:
            net_overlaps.validate()

        self.assertEqual(len(ctx_overlaps.exception.errors), 1)
        err_msg = ctx_overlaps.exception.errors[0]
        expected_overlap = (
            "Allocation 10.0.0.10 (hostname: 'host-a', comment: 'A') overlaps with "
            "10.0.0.10 (hostname: 'host-b', comment: 'B')"
        )
        self.assertIn(expected_overlap, err_msg)

    def test_to_dict_properties(self):
        # 1. Allocation
        alloc = Allocation(ip="10.0.1.10", hostname="host1", comment="Test Alloc")
        alloc_dict = alloc.to_dict
        self.assertEqual(alloc_dict["ip"], "10.0.1.10")
        self.assertEqual(alloc_dict["hostname"], "host1")
        self.assertEqual(alloc_dict["comment"], "Test Alloc")

        # 2. Reservation
        res = Reservation(id="pool1", cidr="10.0.1.10-10.0.1.20", comment="Test Pool", allocatable=True)
        res_dict = res.to_dict
        self.assertEqual(res_dict["id"], "pool1")
        self.assertEqual(res_dict["cidr"], "10.0.1.10-10.0.1.20")
        self.assertEqual(res_dict["comment"], "Test Pool")
        self.assertTrue(res_dict["allocatable"])

        # 3. StaticRoute
        sr = StaticRoute(cidr="172.16.0.0/16", gateway="10.0.1.1")
        sr_dict = sr.to_dict
        self.assertEqual(sr_dict["cidr"], "172.16.0.0/16")
        self.assertEqual(sr_dict["gateway"], "10.0.1.1")

        # 4. Network
        net = Network(
            name="test_net",
            cidr="10.0.1.0/24",
            vlan=30,
            static_routes=[sr],
            reservations=[res],
            allocations=[alloc],
            description="My Network",
        )
        self.assertEqual(net.gateway, "10.0.1.1")
        net_dict = net.to_dict
        self.assertEqual(net_dict["name"], "test_net")
        self.assertEqual(net_dict["cidr"], "10.0.1.0/24")
        self.assertEqual(net_dict["gateway"], "10.0.1.1")
        self.assertEqual(net_dict["vlan"], 30)
        self.assertEqual(net_dict["description"], "My Network")
        self.assertEqual(len(net_dict["static_routes"]), 1)
        self.assertEqual(net_dict["static_routes"][0]["cidr"], "172.16.0.0/16")
        self.assertEqual(len(net_dict["reservations"]), 1)
        self.assertEqual(net_dict["reservations"][0]["id"], "pool1")
        self.assertEqual(len(net_dict["allocations"]), 1)
        self.assertEqual(net_dict["allocations"][0]["ip"], "10.0.1.10")


class TestAggregateNetwork(unittest.TestCase):
    def test_aggregate_properties(self):
        agg = Network(name="agg_net", cidr="10.10.0.0/22", aggregate=True)
        self.assertTrue(agg.aggregate)
        self.assertIsNone(agg.gateway)
        self.assertEqual(agg.effective_reservations, [])
        self.assertTrue(agg.to_dict["aggregate"])

    def test_aggregate_no_direct_allocations(self):
        alloc = Allocation(ip="10.10.0.10", hostname="host1")
        agg = Network(name="agg_net", cidr="10.10.0.0/22", aggregate=True, allocations=[alloc])
        with self.assertRaises(DatabaseValidationError):
            agg.validate()

    def test_validate_aggregate_with_subnets(self):
        agg = Network(name="corp_aggregate", cidr="10.10.0.0/22", aggregate=True)
        sub1 = Network(name="sub1", cidr="10.10.0.0/24", epg="EPG1")
        sub2 = Network(name="sub2", cidr="10.10.1.0/24", epg="EPG2")
        sub3 = Network(name="sub3", cidr="10.10.2.0/24", epg="EPG3")
        sub4 = Network(name="sub4", cidr="10.10.3.0/24", epg="EPG4")

        networks = [agg, sub1, sub2, sub3, sub4]
        # Should pass without errors
        validate_network_list(networks)

        # Check helper methods
        self.assertEqual(len(agg.get_subnets(networks)), 4)
        self.assertEqual(sub1.get_parent_aggregate(networks), agg)
        self.assertEqual(agg.get_unallocated_subnets(networks), [])

    def test_aggregate_partial_subnets_unallocated_capacity(self):
        import ipaddress

        agg = Network(name="corp_aggregate", cidr="10.10.0.0/22", aggregate=True)
        sub1 = Network(name="sub1", cidr="10.10.0.0/24", epg="EPG1")
        sub2 = Network(name="sub2", cidr="10.10.1.0/24", epg="EPG2")
        networks = [agg, sub1, sub2]

        validate_network_list(networks)
        unallocated = agg.get_unallocated_subnets(networks)
        self.assertEqual(unallocated, [ipaddress.ip_network("10.10.2.0/23")])

    def test_aggregate_sibling_overlap_fails(self):
        agg = Network(name="corp_aggregate", cidr="10.10.0.0/22", aggregate=True)
        sub1 = Network(name="sub1", cidr="10.10.0.0/24", epg="EPG1")
        sub2 = Network(name="sub2", cidr="10.10.0.128/25", epg="EPG2")  # Overlaps sub1
        with self.assertRaises(DatabaseValidationError):
            validate_network_list([agg, sub1, sub2])

    def test_network_exceeding_aggregate_boundary_fails(self):
        agg = Network(name="corp_aggregate", cidr="10.10.0.0/22", aggregate=True)
        bad_sub = Network(name="bad_sub", cidr="10.10.0.0/21")  # Larger than aggregate
        with self.assertRaises(DatabaseValidationError):
            validate_network_list([agg, bad_sub])


if __name__ == "__main__":
    unittest.main()
