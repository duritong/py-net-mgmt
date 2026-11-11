import ipaddress
import os
from typing import Any, List, Optional

from .core import Allocation, Network, find_network_for_ip, find_networks_for_cidr, lookup_ip_or_cidr
from .core import query_networks as core_query_networks
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
    from .db import (
        get_bridge_domain_by_name,
        get_datacenter_by_name,
        get_environment_by_name,
        get_epg_by_name,
        get_zone_by_name,
    )

    mapping = {
        "epgs": get_epg_by_name,
        "bridge_domains": get_bridge_domain_by_name,
        "environments": get_environment_by_name,
        "zones": get_zone_by_name,
        "datacenters": get_datacenter_by_name,
    }
    func = mapping.get(subdir)
    if func:
        data = func(name)
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
    """Find the Network object containing a given IP address or CIDR.
    Usage:
        networks | network_containing_ip('10.0.1.10')
        '10.0.1.10' | network_containing_ip
        networks | network_containing_ip('10.0.1.0/24')
        '10.0.1.0/24' | network_containing_ip
    """
    if ip_str is None:
        ip_str = value
        networks = get_database()
    else:
        networks = _ensure_networks(value)

    if not ip_str:
        return None

    target_str = str(ip_str).strip()
    # Try parsing as IP address first
    if "/" not in target_str or target_str.endswith("/32") or target_str.endswith("/128"):
        try:
            target_ip = ipaddress.ip_address(target_str.split("/")[0])
            return find_network_for_ip(target_ip, networks)
        except ValueError:
            pass

    # Try parsing as CIDR network
    try:
        target_net = ipaddress.ip_network(target_str, strict=False)
        nets = find_networks_for_cidr(target_net, networks)
        return nets[0] if nets else None
    except ValueError:
        return None


def network_containing_cidr(value: Any, cidr_str: Optional[str] = None) -> Optional[Network]:
    """Find the Network object containing a given CIDR network.
    Usage:
        networks | network_containing_cidr('10.0.1.0/24')
        '10.0.1.0/24' | network_containing_cidr
    """
    return network_containing_ip(value, cidr_str)


def lookup_target(value: Any, target: Optional[str] = None, context: Optional[str] = None) -> dict:
    """Perform a comprehensive lookup for an IP or CIDR target across networks.
    Usage:
        networks | lookup_target('10.0.1.10')
        '10.0.1.10' | lookup_target
    """
    if target is None:
        target = value
        networks = get_database()
    else:
        networks = _ensure_networks(value)

    return lookup_ip_or_cidr(str(target), networks, context=context)


def ip_info(value: Any, ip_str: Optional[str] = None) -> Optional[dict]:
    """Retrieve detailed IP allocation, reservation, and status information from a Network.
    Usage:
        network | ip_info('10.0.1.10')
    """
    if isinstance(value, Network) and ip_str:
        return value.get_ip_info(ip_str)
    return None


def cidr_info(value: Any, cidr_str: Optional[str] = None) -> Optional[dict]:
    """Retrieve detailed CIDR subnet information from a Network.
    Usage:
        network | cidr_info('10.0.1.16/28')
    """
    if isinstance(value, Network) and cidr_str:
        return value.get_cidr_info(cidr_str)
    return None


def query_networks(value: Any, filters: Optional[dict] = None, **kwargs) -> List[Network]:
    """
    Query and filter networks by attributes.
    Usage:
        networks | query_networks(description='Storage', environment='production')
        networks | query_networks({'description': 'Storage'})
    """
    networks = _ensure_networks(value)
    return core_query_networks(networks, filters=filters, **kwargs)


def jinja_apply_reservation_template(value: Any, template_path: str) -> dict:
    """
    Apply a relative reservation template (YAML file) to a network inside Jinja.
    Usage:
        network | apply_reservation_template('path/to/template.yaml')
    """
    if not isinstance(value, Network):
        return {"applied": [], "skipped": [], "failed": {"error": "Value must be a Network object"}}

    import yaml

    if not os.path.exists(template_path):
        return {"applied": [], "skipped": [], "failed": {"error": f"Template file '{template_path}' not found"}}

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_data = yaml.safe_load(f) or {}
    except Exception as e:
        return {"applied": [], "skipped": [], "failed": {"error": f"Failed to parse template YAML: {e}"}}

    return value.apply_reservation_template(template_data)


def dual_stack_peer(value: Any, all_networks: Optional[List[Network]] = None) -> Optional[Network]:
    """Retrieve the corresponding dual-stack peer network (IPv4 <-> IPv6) under the same EPG or Bridge Domain.
    Usage:
        network | dual_stack_peer
        network | dual_stack_peer(networks)
    """
    if not isinstance(value, Network):
        return None
    nets = _ensure_networks(all_networks)
    return value.get_dual_stack_peer(nets)


def networks_by_ip_version(value: Any, version: int = 4) -> List[Network]:
    """Filter networks by IP version (4 or 6).
    Usage:
        networks | networks_by_ip_version(6)
        get_networks() | networks_by_ip_version(4)
    """
    networks = _ensure_networks(value)
    target_ver = 6 if str(version).lstrip("v") == "6" else 4
    return [n for n in networks if n.cidr.version == target_ver]


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
    env.filters["network_containing_cidr"] = network_containing_cidr
    env.filters["lookup_target"] = lookup_target
    env.filters["ip_info"] = ip_info
    env.filters["cidr_info"] = cidr_info
    env.filters["query_networks"] = query_networks
    env.filters["apply_reservation_template"] = jinja_apply_reservation_template
    env.filters["dual_stack_peer"] = dual_stack_peer
    env.filters["networks_by_ip_version"] = networks_by_ip_version
    env.filters["get_networks"] = get_database  # Keep for compatibility if needed, but globals is better
    env.globals["get_networks"] = get_database
