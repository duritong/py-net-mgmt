import ipaddress
from typing import Any, List, Optional

from .core import Allocation, Network
from .db import get_cached_entities, get_database


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


class RelationalEntity:
    """Wrapper class providing name injection and transitive attribute delegation."""

    def __init__(self, name: str, data: dict, subdir: str):
        self._name = name
        self._data = data or {}
        self._subdir = subdir

    @property
    def name(self) -> str:
        return self._name

    def __getitem__(self, key: str) -> Any:
        if key == "name":
            return self._name
        if key in self._data:
            return self._data[key]
        if key in ("zone", "datacenter"):
            val = getattr(self, key, None)
            if val is not None:
                return val
        raise KeyError(key)

    def __getattr__(self, key: str) -> Any:
        if key in self._data:
            return self._data[key]
        if key in ("zone", "datacenter"):
            if self._subdir == "epgs":
                bd_name = self._data.get("bridge_domain")
                if bd_name:
                    bd = bridge_domain_by_name(bd_name)
                    if bd:
                        return getattr(bd, key, None)
        return None

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def copy(self) -> dict:
        res = self._data.copy()
        res["name"] = self._name
        if self._subdir == "epgs":
            res["zone"] = self.zone
            res["datacenter"] = self.datacenter
        return res


def _lookup_entity(subdir: str, name: str) -> Optional[RelationalEntity]:
    """Helper to lookup relational entity metadata and wrap as RelationalEntity."""
    entities = get_cached_entities(subdir)
    data = entities.get(name)
    if data is not None:
        return RelationalEntity(name, data, subdir)
    return None


def epg_by_name(value: Any, name: Optional[str] = None) -> Optional[RelationalEntity]:
    """Find EPG properties by name (Highly Optimized via In-Memory Cache)."""
    if name is None:
        name = value
    return _lookup_entity("epgs", name)


def bridge_domain_by_name(value: Any, name: Optional[str] = None) -> Optional[RelationalEntity]:
    """Find Bridge Domain properties by name (Highly Optimized via In-Memory Cache)."""
    if name is None:
        name = value
    return _lookup_entity("bridge_domains", name)


def environment_by_name(value: Any, name: Optional[str] = None) -> Optional[RelationalEntity]:
    """Find Environment properties by name (Highly Optimized via In-Memory Cache)."""
    if name is None:
        name = value
    return _lookup_entity("environments", name)


def zone_by_name(value: Any, name: Optional[str] = None) -> Optional[RelationalEntity]:
    """Find Zone properties by name (Highly Optimized via In-Memory Cache)."""
    if name is None:
        name = value
    return _lookup_entity("zones", name)


def datacenter_by_name(value: Any, name: Optional[str] = None) -> Optional[RelationalEntity]:
    """Find Datacenter properties by name (Highly Optimized via In-Memory Cache)."""
    if name is None:
        name = value
    return _lookup_entity("datacenters", name)


def network_containing_ip(value: Any, ip_str: Optional[str] = None) -> Optional[Network]:
    """Find the Network object containing a given IP address.
    Usage:
        networks | network_containing_ip('10.0.1.10')
        '10.0.1.10' | network_containing_ip
    """
    if ip_str is None:
        ip_str = value
        networks = get_database()
    else:
        networks = _ensure_networks(value)

    try:
        target_ip = ipaddress.ip_address(str(ip_str))
    except ValueError:
        return None

    for net in networks:
        if target_ip in net.cidr:
            return net
    return None


def query_networks(value: Any, filters: Optional[dict] = None, **kwargs) -> List[Network]:
    """
    Query and filter networks by attributes.
    Usage:
        networks | query_networks(description='Storage', environment='production')
        networks | query_networks({'description': 'Storage'})
    """
    networks = _ensure_networks(value)

    # Merge filters dict with kwargs
    query_params = {}
    if isinstance(filters, dict):
        query_params.update(filters)
    query_params.update(kwargs)

    if not query_params:
        return networks

    filtered = []
    for net in networks:
        match = True
        for key, val in query_params.items():
            if val is None:
                continue

            # Special case: description does substring matching
            if key == "description":
                if not net.description or val.lower() not in net.description.lower():
                    match = False
                    break
            else:
                # Standard attributes do exact case-insensitive matching (or direct matches)
                attr_val = getattr(net, key, None)
                if attr_val is None:
                    match = False
                    break

                if isinstance(attr_val, str) and isinstance(val, str):
                    if attr_val.lower() != val.lower():
                        match = False
                        break
                elif attr_val != val:
                    match = False
                    break
        if match:
            filtered.append(net)

    return filtered


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
    env.filters["network_containing_ip"] = network_containing_ip
    env.filters["query_networks"] = query_networks
    env.filters["get_networks"] = get_database  # Keep for compatibility if needed, but globals is better
    env.globals["get_networks"] = get_database
