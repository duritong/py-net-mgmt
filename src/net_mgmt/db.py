import os
from typing import List, Optional

from .core import Network, validate_network_list
from .loader import load_all_networks, load_yaml_files_from_subdir

_DB_CACHE: Optional[List[Network]] = None
_DB_PATH: str = os.environ.get("NET_MGMT_PATH", "networks")
_ENTITY_CACHE: dict = {}  # Maps (db_path, subdir) -> {"data": data, "mtime": float}


def set_db_path(path: str):
    global _DB_PATH, _DB_CACHE, _ENTITY_CACHE
    if _DB_PATH != path:
        _DB_PATH = path
        _DB_CACHE = None  # Invalidate cache when path changes
        _ENTITY_CACHE.clear()


def get_db_path() -> str:
    global _DB_PATH
    return _DB_PATH


def get_cached_entities(subdir: str) -> dict:
    """Retrieve relational entities with filesystem-level freshness tracking (mtime)."""
    global _ENTITY_CACHE, _DB_PATH
    path = os.path.join(_DB_PATH, subdir)
    if not os.path.isdir(path):
        return {}

    # Gather mtimes of the directory and all yaml files to track freshness
    mtimes = [os.path.getmtime(path)]
    for file in os.listdir(path):
        if file.lower().endswith(".yaml"):
            mtimes.append(os.path.getmtime(os.path.join(path, file)))
    current_max_mtime = max(mtimes) if mtimes else 0.0

    key = (_DB_PATH, subdir)
    cached = _ENTITY_CACHE.get(key)
    if not cached or cached["mtime"] != current_max_mtime:
        data = load_yaml_files_from_subdir(_DB_PATH, subdir)
        _ENTITY_CACHE[key] = {"data": data, "mtime": current_max_mtime}

    return _ENTITY_CACHE[key]["data"]


def clear_db_cache():
    """Manually clear all in-memory database and entity caches."""
    global _DB_CACHE, _ENTITY_CACHE
    _DB_CACHE = None
    _ENTITY_CACHE.clear()


def get_epg_by_name(name: str) -> Optional[dict]:
    """Retrieve EPG properties by name programmatically."""
    return get_cached_entities("epgs").get(name)


def get_bridge_domain_by_name(name: str) -> Optional[dict]:
    """Retrieve Bridge Domain properties by name programmatically."""
    return get_cached_entities("bridge_domains").get(name)


def get_environment_by_name(name: str) -> Optional[dict]:
    """Retrieve Environment properties by name programmatically."""
    return get_cached_entities("environments").get(name)


def get_zone_by_name(name: str) -> Optional[dict]:
    """Retrieve Zone properties by name programmatically."""
    return get_cached_entities("zones").get(name)


def get_datacenter_by_name(name: str) -> Optional[dict]:
    """Retrieve Datacenter properties by name programmatically."""
    return get_cached_entities("datacenters").get(name)


def get_database(force_reload: bool = False) -> List[Network]:
    global _DB_CACHE
    if _DB_CACHE is None or force_reload:
        networks = load_all_networks(_DB_PATH)
        validate_network_list(networks)
        _DB_CACHE = networks
    return _DB_CACHE
