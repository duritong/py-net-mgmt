import ipaddress
from dataclasses import dataclass, field
from typing import Generator, List, Optional, Union


@dataclass
class Allocation:
    ip: Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]] = None
    hostname: Optional[str] = None
    cidr: Optional[str] = None  # Can be CIDR or range "start-end"
    comment: Optional[str] = None
    _networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = field(init=False, repr=False)

    def __post_init__(self):
        self._networks = []
        if self.ip:
            if isinstance(self.ip, str):
                self.ip = ipaddress.ip_address(self.ip)
            if not self.hostname:
                raise ValueError("Hostname is mandatory for single IP allocations")
            # Create a /32 or /128 network for consistent handling
            self._networks = [ipaddress.ip_network(f"{self.ip}/{self.ip.max_prefixlen}")]

        elif self.cidr:
            if not self.comment:
                raise ValueError("Comment is mandatory for subnet/range allocations")

            definition = str(self.cidr).strip()
            if "-" in definition:
                try:
                    start_str, end_str = map(str.strip, definition.split("-"))
                    start_ip = ipaddress.ip_address(start_str)
                    end_ip = ipaddress.ip_address(end_str)
                    self._networks = list(ipaddress.summarize_address_range(start_ip, end_ip))
                except ValueError as e:
                    raise ValueError(f"Invalid range format '{definition}': {e}")
            else:
                try:
                    net = ipaddress.ip_network(definition, strict=False)
                    self._networks = [net]
                except ValueError:
                    raise ValueError(f"Invalid allocation format '{definition}'")
        else:
            raise ValueError("Allocation must have either 'ip' or 'cidr'")

    @property
    def networks(self) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        return self._networks


@dataclass
class Reservation:
    id: str
    cidr: str  # Kept name 'cidr' for compatibility, but acts as definition
    comment: str
    allocatable: bool = False
    _networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = field(init=False, repr=False)

    def __post_init__(self):
        self._networks = []
        definition = str(self.cidr).strip()

        if "-" in definition:
            # Handle range: "start_ip - end_ip"
            try:
                start_str, end_str = map(str.strip, definition.split("-"))
                start_ip = ipaddress.ip_address(start_str)
                end_ip = ipaddress.ip_address(end_str)
                # summarize_address_range returns an iterator
                self._networks = list(ipaddress.summarize_address_range(start_ip, end_ip))
            except ValueError as e:
                raise ValueError(f"Invalid range format '{definition}': {e}")
        else:
            # Handle single IP or CIDR
            try:
                # Try as network first (CIDR)
                net = ipaddress.ip_network(definition, strict=False)
                self._networks = [net]
            except ValueError:
                try:
                    # Try as single IP
                    addr = ipaddress.ip_address(definition)
                    # Convert single IP to /32 or /128 network
                    net = ipaddress.ip_network(f"{addr}/{addr.max_prefixlen}")
                    self._networks = [net]
                except ValueError:
                    raise ValueError(f"Invalid reservation format '{definition}'")

    @property
    def networks(self) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        return self._networks

    @property
    def num_addresses(self) -> int:
        return sum(net.num_addresses for net in self.networks)

    def overlaps(self, other: "Reservation") -> bool:
        for net1 in self.networks:
            for net2 in other.networks:
                if net1.overlaps(net2):
                    return True
        return False

    def contains_ip(self, ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
        for net in self.networks:
            if ip in net:
                return True
        return False

    def contains_network(self, other_net: Union[ipaddress.IPv4Network, ipaddress.IPv6Network]) -> bool:
        for net in self.networks:
            if other_net.subnet_of(net):
                return True
        return False

    def iter_ips(self) -> Generator[Union[ipaddress.IPv4Address, ipaddress.IPv6Address], None, None]:
        for net in self.networks:
            for ip in net:
                yield ip


@dataclass
class Network:
    name: str
    cidr: Union[ipaddress.IPv4Network, ipaddress.IPv6Network]
    vlan: Optional[int] = None
    bridge_domain: Optional[str] = None
    epg: Optional[str] = None
    zone: Optional[str] = None
    datacenter: Optional[str] = None
    routable: bool = True
    context: str = "default"
    description: Optional[str] = None
    file_path: Optional[str] = None
    reservations: List[Reservation] = field(default_factory=list)
    allocations: List[Allocation] = field(default_factory=list)
    reserve_gateway: bool = True
    reserve_internal: bool = True

    def __post_init__(self):
        if isinstance(self.cidr, str):
            self.cidr = ipaddress.ip_network(self.cidr, strict=False)

    def _get_system_reservations(self) -> List[Reservation]:
        sys_res = []

        # Always reserve network address
        sys_res.append(
            Reservation(
                id="sys-network",
                cidr=str(self.cidr.network_address),
                comment="network address",
                allocatable=False,
            )
        )

        # Always reserve broadcast address for IPv4
        if isinstance(self.cidr, ipaddress.IPv4Network):
            if self.cidr.broadcast_address != self.cidr.network_address:
                sys_res.append(
                    Reservation(
                        id="sys-broadcast",
                        cidr=str(self.cidr.broadcast_address),
                        comment="broadcast address",
                        allocatable=False,
                    )
                )

        if isinstance(self.cidr, ipaddress.IPv4Network):
            # Logic primarily for IPv4, IPv6 is more complex with gateways/internal
            # Assuming IPv4 for the specific +1 +4 logic as is common
            first_ip = self.cidr.network_address

            if self.reserve_gateway:
                gw_ip = first_ip + 1
                if gw_ip in self.cidr:
                    sys_res.append(
                        Reservation(
                            id="sys-gateway",
                            cidr=str(gw_ip),
                            comment="network internal",
                            allocatable=False,
                        )
                    )

            if self.reserve_internal:
                start_int = first_ip + 2
                end_int = first_ip + 5
                if start_int in self.cidr and end_int in self.cidr:
                    sys_res.append(
                        Reservation(
                            id="sys-internal",
                            cidr=f"{start_int}-{end_int}",
                            comment="network internal",
                            allocatable=False,
                        )
                    )
                elif start_int in self.cidr:
                    # Partial overlap with end of subnet
                    hosts = list(self.cidr.hosts())
                    if hosts:
                        last_host = hosts[-1]
                        effective_end = min(end_int, last_host)
                        if start_int <= effective_end:
                            sys_res.append(
                                Reservation(
                                    id="sys-internal",
                                    cidr=f"{start_int}-{effective_end}",
                                    comment="network internal",
                                    allocatable=False,
                                )
                            )
        return sys_res

    @property
    def effective_reservations(self) -> List[Reservation]:
        return self.reservations + self._get_system_reservations()

    def get_unreserved_ranges(self) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        """Calculate network ranges not covered by any reservation."""
        free_nets = [self.cidr]
        reservations = self.effective_reservations

        for res in reservations:
            for res_net in res.networks:
                new_free_nets = []
                for free_net in free_nets:
                    if res_net.overlaps(free_net):
                        if res_net == free_net:
                            # Fully consumed
                            pass
                        elif res_net.subnet_of(free_net):
                            # res_net is strictly inside free_net
                            try:
                                new_free_nets.extend(free_net.address_exclude(res_net))
                            except ValueError:
                                # Should not happen if subnet_of check passed and strictness matches
                                pass
                        elif free_net.subnet_of(res_net):
                            # free_net is fully covered by res_net
                            pass
                        else:
                            # Should be impossible for CIDR blocks
                            pass
                    else:
                        new_free_nets.append(free_net)
                free_nets = new_free_nets

        return sorted(free_nets, key=lambda x: x.network_address)

    def get_reservation_usage(self, reservation_id: str):
        """Get usage statistics for a reservation."""
        res = next((r for r in self.effective_reservations if r.id == reservation_id), None)
        if not res:
            return None

        # Let's count Allocation objects for 'count', and addresses for 'percent'
        alloc_obj_count = 0
        used_addresses = 0

        for alloc in self.allocations:
            is_in_res = False
            for alloc_net in alloc.networks:
                if res.contains_network(alloc_net):
                    is_in_res = True
                    used_addresses += alloc_net.num_addresses
            if is_in_res:
                alloc_obj_count += 1

        total = res.num_addresses
        percent = (used_addresses / total * 100) if total > 0 else 0

        return {"count": alloc_obj_count, "total": total, "percent": percent}

    def query_allocations(self, prefix: str) -> List[Allocation]:
        """Query allocations by IP prefix, CIDR, hostname prefix, or comment prefix."""
        results = []
        prefix_lower = prefix.lower()

        for alloc in self.allocations:
            # Check IP/CIDR matches (as string prefix)
            if alloc.ip and str(alloc.ip).startswith(prefix):
                results.append(alloc)
                continue
            if alloc.cidr and alloc.cidr.startswith(prefix):
                results.append(alloc)
                continue

            # Check hostname/comment matches
            if alloc.hostname and alloc.hostname.lower().startswith(prefix_lower):
                results.append(alloc)
                continue
            if alloc.comment and alloc.comment.lower().startswith(prefix_lower):
                results.append(alloc)
                continue

        return results

    def validate(self):
        """Validate network configuration and reservations."""
        eff_reservations = self.effective_reservations

        for reservation in eff_reservations:
            # Check if all parts of the reservation are within network CIDR
            for res_net in reservation.networks:
                if not res_net.subnet_of(self.cidr):
                    raise ValueError(
                        f"Reservation {reservation.cidr} (part {res_net}) is not within network CIDR {self.cidr}"
                    )

        # Check for overlapping reservations
        for i in range(len(eff_reservations)):
            for j in range(i + 1, len(eff_reservations)):
                # Skip checking system reservations against themselves if they are designed to not overlap
                # But here we just check everything against everything
                if eff_reservations[i].overlaps(eff_reservations[j]):
                    raise ValueError(
                        f"Reservation '{eff_reservations[i].id}' ({eff_reservations[i].cidr}) "
                        f"overlaps with '{eff_reservations[j].id}' ({eff_reservations[j].cidr})"
                    )

        # Validate Allocations
        for alloc in self.allocations:
            for alloc_net in alloc.networks:
                if not alloc_net.subnet_of(self.cidr):
                    raise ValueError(f"Allocation {alloc_net} is not within network CIDR {self.cidr}")

                # Must be in an allocatable reservation
                found_res = False
                for res in eff_reservations:
                    if res.allocatable and res.contains_network(alloc_net):
                        found_res = True
                        break
                if not found_res:
                    raise ValueError(f"Allocation {alloc.cidr or alloc.ip} is not within any allocatable reservation")

            # Check for Duplicate Allocations (overlap check)
            # Compare this alloc against all other allocs
            for other_alloc in self.allocations:
                if alloc is other_alloc:
                    continue
                for net1 in alloc.networks:
                    for net2 in other_alloc.networks:
                        if net1.overlaps(net2):
                            raise ValueError(
                                f"Allocation {alloc.cidr or alloc.ip} overlaps with "
                                f"{other_alloc.cidr or other_alloc.ip}"
                            )

    def add_reservation(self, id: str, cidr: str, comment: str, allocatable: bool = False):
        reservation = Reservation(id=id, cidr=cidr, comment=comment, allocatable=allocatable)
        self.reservations.append(reservation)
        self.validate()

    def get_next_free_ip(self, reservation_id: Optional[str] = None) -> ipaddress.IPv4Address:
        target_reservations = []
        eff_reservations = self.effective_reservations

        if reservation_id:
            res = next((r for r in eff_reservations if r.id == reservation_id), None)
            if not res:
                raise ValueError(f"Reservation '{reservation_id}' not found")
            if not res.allocatable:
                raise ValueError(f"Reservation '{reservation_id}' is not allocatable")
            target_reservations = [res]
        else:
            # Filter allocatable reservations
            target_reservations = [r for r in eff_reservations if r.allocatable]
            if not target_reservations:
                raise ValueError("No allocatable reservations found")

        allocated_ips = {a.ip for a in self.allocations}

        for res in target_reservations:
            for ip in res.iter_ips():
                if ip not in allocated_ips:
                    return ip

        raise ValueError("No free IPs available")

    def save(self):
        if self.file_path:
            from .loader import save_network_to_file

            save_network_to_file(self)

    def add_allocation(self, allocation: Allocation):
        self.allocations.append(allocation)
        self.validate()
        self.save()

    def find_or_allocate_hostname(self, hostname: str, reservation_id: Optional[str] = None) -> Allocation:
        for alloc in self.allocations:
            if alloc.hostname == hostname:
                return alloc

        ip = self.get_next_free_ip(reservation_id)
        alloc = Allocation(ip=ip, hostname=hostname)
        self.allocations.append(alloc)
        self.validate()
        self.save()
        return alloc

    def find_or_allocate_range(
        self, comment: str, count: int, reservation_id: Optional[str] = None
    ) -> List[Allocation]:
        existing = [a for a in self.allocations if a.comment == comment]

        current_count = 0
        for a in existing:
            for net in a.networks:
                if net.prefixlen == net.max_prefixlen:
                    current_count += 1
                else:
                    current_count += net.num_addresses

        if current_count == count:
            return existing
        elif current_count > count:
            raise ValueError(f"More allocations found ({current_count}) for '{comment}' than requested ({count})")

        needed = count - current_count

        eff_reservations = self.effective_reservations
        if reservation_id:
            res = next((r for r in eff_reservations if r.id == reservation_id), None)
            if not res or not res.allocatable:
                raise ValueError(f"Reservation '{reservation_id}' not found or not allocatable")
            target_reservations = [res]
        else:
            target_reservations = [r for r in eff_reservations if r.allocatable]

        allocated_ips = set()
        for alloc in self.allocations:
            for net in alloc.networks:
                for ip in net:
                    allocated_ips.add(ip)

        free_ips_set = set()
        for res in target_reservations:
            for ip in res.iter_ips():
                if ip not in allocated_ips:
                    free_ips_set.add(ip)

        if len(free_ips_set) < needed:
            raise ValueError(
                f"Not enough free IPs. Requested {count}, missing {needed}, "
                f"but only {len(free_ips_set)} available in reservations."
            )

        existing_ips = []
        for a in existing:
            for net in a.networks:
                for ip in net:
                    existing_ips.append(ip)

        existing_ips.sort()
        allocated_new_ips = []

        if existing_ips:
            next_ip = existing_ips[-1] + 1
            while needed > 0 and next_ip in free_ips_set:
                allocated_new_ips.append(next_ip)
                free_ips_set.remove(next_ip)
                needed -= 1
                next_ip += 1

        if needed > 0:
            remaining_free = sorted(list(free_ips_set))
            current_block = []
            best_block = []
            for ip in remaining_free:
                if not current_block:
                    current_block = [ip]
                elif int(ip) == int(current_block[-1]) + 1:
                    current_block.append(ip)
                else:
                    if len(current_block) >= needed:
                        best_block = current_block[:needed]
                        break
                    current_block = [ip]

            if len(current_block) >= needed:
                best_block = current_block[:needed]

            if best_block:
                allocated_new_ips.extend(best_block)
                for ip in best_block:
                    free_ips_set.remove(ip)
                needed -= len(best_block)

        if needed > 0:
            remaining_free = sorted(list(free_ips_set))
            allocated_new_ips.extend(remaining_free[:needed])
            needed = 0

        if allocated_new_ips:
            allocated_new_ips.sort()
            ranges = []
            start = allocated_new_ips[0]
            prev = start
            for ip in allocated_new_ips[1:]:
                if int(ip) == int(prev) + 1:
                    prev = ip
                else:
                    ranges.append((start, prev))
                    start = ip
                    prev = ip
            ranges.append((start, prev))

            new_allocs = []
            for s, e in ranges:
                if s == e:
                    new_allocs.append(Allocation(cidr=str(s), comment=comment))
                else:
                    new_allocs.append(Allocation(cidr=f"{s}-{e}", comment=comment))

            self.allocations.extend(new_allocs)
            existing.extend(new_allocs)
            self.validate()
            self.save()

        return existing

    def delete_allocations(
        self,
        ip: Optional[str] = None,
        hostname: Optional[str] = None,
        comment: Optional[str] = None,
        cidr: Optional[str] = None,
    ) -> int:
        initial_len = len(self.allocations)
        new_allocs = []
        for alloc in self.allocations:
            match = False
            if ip and alloc.ip and str(alloc.ip) == ip:
                match = True
            elif hostname and alloc.hostname and alloc.hostname == hostname:
                match = True
            elif comment and alloc.comment and alloc.comment == comment:
                match = True
            elif cidr and alloc.cidr and alloc.cidr == cidr:
                match = True

            if not match:
                new_allocs.append(alloc)

        self.allocations = new_allocs
        deleted = initial_len - len(self.allocations)
        if deleted > 0:
            self.save()
        return deleted


def validate_network_list(networks: List[Network]):
    """Validate that routable networks and networks within the same context do not overlap."""

    def check_overlaps(nets: List[Network], group_name: str):
        sorted_networks = sorted(nets, key=lambda x: x.cidr)
        for i in range(len(sorted_networks)):
            for j in range(i + 1, len(sorted_networks)):
                net1 = sorted_networks[i]
                net2 = sorted_networks[j]
                if net1.cidr.overlaps(net2.cidr):
                    raise ValueError(
                        f"Network '{net1.name}' ({net1.cidr}) overlaps with '{net2.name}' ({net2.cidr}) in {group_name}"
                    )

    # Check for overlapping CIDRs between routable networks (they effectively share a global context)
    routable_networks = [n for n in networks if n.routable]
    check_overlaps(routable_networks, "global routable context")

    # Group networks by their context
    context_groups = {}
    for net in networks:
        context_groups.setdefault(net.context, []).append(net)

    for ctx, nets in context_groups.items():
        check_overlaps(nets, f"context '{ctx}'")
