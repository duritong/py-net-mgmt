from typing import Any, List, Optional

from .core import Allocation, Network
from .db import get_database


def _ensure_networks(value: Any) -> List[Network]:
    """Helper to get networks from value or global DB."""
    if isinstance(value, list) and all(isinstance(x, Network) for x in value):
        return value
    return get_database()


def network_by_name(value: Any, name: Optional[str] = None) -> Optional[Network]:
    """Find a network by name. Usage: networks | network_by_name('name') OR 'name' | network_by_name"""
    if name is None:
        # Usage: 'name' | network_by_name
        name = value
        networks = get_database()
    else:
        # Usage: networks | network_by_name('name')
        networks = _ensure_networks(value)

    for network in networks:
        if network.name == name:
            return network
    return None


def networks_in_bridge_domain(value: Any, bridge_domain: Optional[str] = None) -> List[Network]:
    """
    Find all networks in a bridge domain.
    Usage: networks | networks_in_bridge_domain('BD') OR 'BD' | networks_in_bridge_domain
    """
    if bridge_domain is None:
        bridge_domain = value
        networks = get_database()
    else:
        networks = _ensure_networks(value)

    return [n for n in networks if n.bridge_domain == bridge_domain]


def networks_in_epg(value: Any, epg: Optional[str] = None) -> List[Network]:
    """Find all networks in an EPG. Usage: networks | networks_in_epg('EPG') OR 'EPG' | networks_in_epg"""
    if epg is None:
        epg = value
        networks = get_database()
    else:
        networks = _ensure_networks(value)

    return [n for n in networks if n.epg == epg]


def query_allocations(value: Any, prefix: str) -> List[Allocation]:
    """Query allocations by prefix in a network. Usage: network | query_allocations('prefix')"""
    if isinstance(value, Network):
        return value.query_allocations(prefix)
    return []


def find_or_allocate_hostname(
    value: Any, hostname: str, reservation_id: Optional[str] = None
) -> Optional[Allocation]:
    """Find or allocate a single IP by hostname in a network."""
    if isinstance(value, Network):
        alloc = value.find_or_allocate_hostname(hostname, reservation_id)
        return alloc
    return None


def find_or_allocate_range(
    value: Any, comment: str, count: int, reservation_id: Optional[str] = None
) -> List[Allocation]:
    """Find or allocate a range of IPs by comment in a network."""
    if isinstance(value, Network):
        allocs = value.find_or_allocate_range(comment, count, reservation_id)
        return allocs
    return []


def register_filters(env):
    """Register filters to a Jinja2 environment."""
    env.filters["network_by_name"] = network_by_name
    env.filters["networks_in_bridge_domain"] = networks_in_bridge_domain
    env.filters["networks_in_epg"] = networks_in_epg
    env.filters["query_allocations"] = query_allocations
    env.filters["find_or_allocate_hostname"] = find_or_allocate_hostname
    env.filters["find_or_allocate_range"] = find_or_allocate_range
    env.filters["get_networks"] = get_database  # Keep for compatibility if needed, but globals is better
    env.globals["get_networks"] = get_database
