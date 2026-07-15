from typing import Any, List, Optional

from .core import Allocation, Network
from .db import get_database, get_db_path
from .loader import load_yaml_files_from_subdir


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


def find_or_allocate_hostname(value: Any, hostname: str, reservation_id: Optional[str] = None) -> Optional[Allocation]:
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


def jinja_query_vlans(
    value: Any,
    environment: Optional[str] = None,
    zone: Optional[str] = None,
    datacenter: Optional[str] = None,
    bridge_domain: Optional[str] = None,
    epg: Optional[str] = None,
) -> List[int]:
    """
    Query VLANs based on a dictionary of filters or keyword filters.
    Usage:
        networks | query_vlans(environment='prod', zone='trusted')
        { 'environment': 'prod', 'zone': 'trusted' } | query_vlans
    """
    from .core import query_vlans as core_query_vlans

    if isinstance(value, dict):
        networks = get_database()
        return core_query_vlans(
            networks,
            environment=value.get("environment"),
            zone=value.get("zone"),
            datacenter=value.get("datacenter"),
            bridge_domain=value.get("bridge_domain"),
            epg=value.get("epg"),
        )
    else:
        networks = _ensure_networks(value)
        return core_query_vlans(
            networks,
            environment=environment,
            zone=zone,
            datacenter=datacenter,
            bridge_domain=bridge_domain,
            epg=epg,
        )


def vlans_in_environment(value: Any, environment: Optional[str] = None) -> List[int]:
    """
    Retrieve all VLANs defined in a specific environment.
    Usage:
        networks | vlans_in_environment('production')
        'production' | vlans_in_environment
    """
    if environment is None:
        environment = value
        networks = get_database()
    else:
        networks = _ensure_networks(value)

    from .core import query_vlans as core_query_vlans

    return core_query_vlans(networks, environment=environment)


def epg_by_name(value: Any, name: Optional[str] = None) -> Optional[dict]:
    """Find EPG properties by name. Usage: 'EPG_App' | epg_by_name"""
    if name is None:
        name = value
    db_path = get_db_path()
    epgs = load_yaml_files_from_subdir(db_path, "epgs")
    return epgs.get(name)


def bridge_domain_by_name(value: Any, name: Optional[str] = None) -> Optional[dict]:
    """Find Bridge Domain properties by name. Usage: 'BD_Prod' | bridge_domain_by_name"""
    if name is None:
        name = value
    db_path = get_db_path()
    bds = load_yaml_files_from_subdir(db_path, "bridge_domains")
    return bds.get(name)


def environment_by_name(value: Any, name: Optional[str] = None) -> Optional[dict]:
    """Find Environment properties by name. Usage: 'production' | environment_by_name"""
    if name is None:
        name = value
    db_path = get_db_path()
    envs = load_yaml_files_from_subdir(db_path, "environments")
    return envs.get(name)


def zone_by_name(value: Any, name: Optional[str] = None) -> Optional[dict]:
    """Find Zone properties by name. Usage: 'Trusted' | zone_by_name"""
    if name is None:
        name = value
    db_path = get_db_path()
    zones = load_yaml_files_from_subdir(db_path, "zones")
    return zones.get(name)


def datacenter_by_name(value: Any, name: Optional[str] = None) -> Optional[dict]:
    """Find Datacenter properties by name. Usage: 'DC_Frankfurt' | datacenter_by_name"""
    if name is None:
        name = value
    db_path = get_db_path()
    dcs = load_yaml_files_from_subdir(db_path, "datacenters")
    return dcs.get(name)


def register_filters(env):
    """Register filters to a Jinja2 environment."""
    env.filters["network_by_name"] = network_by_name
    env.filters["networks_in_bridge_domain"] = networks_in_bridge_domain
    env.filters["networks_in_epg"] = networks_in_epg
    env.filters["query_allocations"] = query_allocations
    env.filters["find_or_allocate_hostname"] = find_or_allocate_hostname
    env.filters["find_or_allocate_range"] = find_or_allocate_range
    env.filters["query_vlans"] = jinja_query_vlans
    env.filters["vlans_in_environment"] = vlans_in_environment
    env.filters["epg_by_name"] = epg_by_name
    env.filters["bridge_domain_by_name"] = bridge_domain_by_name
    env.filters["environment_by_name"] = environment_by_name
    env.filters["zone_by_name"] = zone_by_name
    env.filters["datacenter_by_name"] = datacenter_by_name
    env.filters["get_networks"] = get_database  # Keep for compatibility if needed, but globals is better
    env.globals["get_networks"] = get_database
