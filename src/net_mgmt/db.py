import os
from typing import List, Optional

from .core import Network, validate_network_list
from .loader import load_all_networks

_DB_CACHE: Optional[List[Network]] = None
_DB_PATH: str = os.environ.get("NET_MGMT_PATH", "networks")


def set_db_path(path: str):
    global _DB_PATH, _DB_CACHE
    if _DB_PATH != path:
        _DB_PATH = path
        _DB_CACHE = None  # Invalidate cache when path changes


def get_database(force_reload: bool = False) -> List[Network]:
    global _DB_CACHE
    if _DB_CACHE is None or force_reload:
        networks = load_all_networks(_DB_PATH)
        validate_network_list(networks)
        _DB_CACHE = networks
    return _DB_CACHE
