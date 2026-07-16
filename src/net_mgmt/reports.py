import os
from typing import List, Optional

import jinja2

from .core import Network
from .db import get_cached_entities, set_db_path

# Resolve the absolute path of the bundled default templates directory
DEFAULT_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def generate_markdown_report(networks: List[Network], output_dir: str, templates_dir: Optional[str] = None):
    os.makedirs(output_dir, exist_ok=True)

    # Sort networks hierarchically: Datacenter -> Zone -> Bridge Domain -> Environment -> EPG -> Subnet
    def get_sort_key(net: Network):
        dc_val = net.datacenter or ""
        dc_key = (dc_val == "", dc_val.lower())

        zone_val = net.zone or ""
        zone_key = (zone_val == "", zone_val.lower())

        bd_val = net.bridge_domain or ""
        bd_key = (bd_val == "", bd_val.lower())

        env_val = net.environment or ""
        env_key = (env_val == "", env_val.lower())

        epg_val = net.epg or ""
        epg_key = (epg_val == "", epg_val.lower())

        name_val = net.name or ""
        name_key = (name_val == "", name_val.lower())

        return (dc_key, zone_key, bd_key, env_key, epg_key, name_key)

    sorted_networks = sorted(networks, key=get_sort_key)

    # 1. Determine DB dir to fetch relational metadata definitions
    if sorted_networks and sorted_networks[0].file_path:
        db_dir = os.path.dirname(os.path.dirname(sorted_networks[0].file_path))
    else:
        db_dir = "networks"

    # 2. Configure Jinja2 environment loaders: user folder overrides -> bundled defaults
    loaders = []
    if templates_dir and os.path.isdir(templates_dir):
        loaders.append(jinja2.FileSystemLoader(templates_dir))
    loaders.append(jinja2.FileSystemLoader(DEFAULT_TEMPLATES_DIR))

    env = jinja2.Environment(loader=jinja2.ChoiceLoader(loaders))

    # 3. Create relational subdirectories under output_dir
    subdirs = ["datacenters", "zones", "environments", "bridge_domains", "epgs", "networks"]
    for subdir in subdirs:
        os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)

    # 4. Load raw metadata files to render complete list of entities (highly optimized via cache)
    set_db_path(db_dir)
    datacenters = get_cached_entities("datacenters")
    zones = get_cached_entities("zones")
    environments = get_cached_entities("environments")
    bridge_domains = get_cached_entities("bridge_domains")
    epgs = get_cached_entities("epgs")

    # Group networks by entity associations
    dc_networks = {}
    zone_networks = {}
    env_networks = {}
    bd_networks = {}
    epg_networks = {}

    for net in sorted_networks:
        if net.datacenter:
            dc_networks.setdefault(net.datacenter, []).append(net)
        if net.zone:
            zone_networks.setdefault(net.zone, []).append(net)
        if net.environment:
            env_networks.setdefault(net.environment, []).append(net)
        if net.bridge_domain:
            bd_networks.setdefault(net.bridge_domain, []).append(net)
        if net.epg:
            epg_networks.setdefault(net.epg, []).append(net)

    # 5. Render Datacenters
    for dc_name, dc_props in datacenters.items():
        nets = dc_networks.get(dc_name, [])
        content = env.get_template("datacenter.md").render(name=dc_name, properties=dc_props, networks=nets)
        with open(os.path.join(output_dir, "datacenters", f"{dc_name}.md"), "w", encoding="utf-8") as f:
            f.write(content)

    # Render Zones
    for zone_name, zone_props in zones.items():
        nets = zone_networks.get(zone_name, [])
        content = env.get_template("zone.md").render(name=zone_name, properties=zone_props, networks=nets)
        with open(os.path.join(output_dir, "zones", f"{zone_name}.md"), "w", encoding="utf-8") as f:
            f.write(content)

    # Render Environments
    for env_name, env_props in environments.items():
        nets = env_networks.get(env_name, [])
        content = env.get_template("environment.md").render(name=env_name, properties=env_props, networks=nets)
        with open(os.path.join(output_dir, "environments", f"{env_name}.md"), "w", encoding="utf-8") as f:
            f.write(content)

    # Render Bridge Domains
    for bd_name, bd_props in bridge_domains.items():
        nets = bd_networks.get(bd_name, [])
        content = env.get_template("bridge_domain.md").render(name=bd_name, properties=bd_props, networks=nets)
        with open(os.path.join(output_dir, "bridge_domains", f"{bd_name}.md"), "w", encoding="utf-8") as f:
            f.write(content)

    # Render EPGs
    for epg_name, epg_props in epgs.items():
        nets = epg_networks.get(epg_name, [])
        content = env.get_template("epg.md").render(name=epg_name, properties=epg_props, networks=nets)
        with open(os.path.join(output_dir, "epgs", f"{epg_name}.md"), "w", encoding="utf-8") as f:
            f.write(content)

    # Render Networks
    for net in sorted_networks:
        content = env.get_template("network.md").render(network=net)
        with open(os.path.join(output_dir, "networks", f"{net.name}.md"), "w", encoding="utf-8") as f:
            f.write(content)

    # 6. Render Index (README.md) using Option B nested list structure
    tree = {}
    unassigned_networks = []

    for net in sorted_networks:
        if not (net.datacenter or net.zone or net.bridge_domain or net.environment or net.epg):
            unassigned_networks.append(net)
        else:
            dc = net.datacenter or "unassigned"
            zone = net.zone or "unassigned"
            bd = net.bridge_domain or "unassigned"
            env_val = net.environment or "unassigned"
            epg = net.epg or "unassigned"

            tree.setdefault(dc, {}).setdefault(zone, {}).setdefault(bd, {}).setdefault(env_val, {}).setdefault(
                epg, []
            ).append(net)

    content = env.get_template("index.md").render(tree=tree, unassigned_networks=unassigned_networks)
    with open(os.path.join(output_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(content)

    # 7. Render indices (README.md) inside each sub-directory
    # Datacenters Index
    content = env.get_template("datacenter_index.md").render(datacenters=datacenters)
    with open(os.path.join(output_dir, "datacenters", "README.md"), "w", encoding="utf-8") as f:
        f.write(content)

    # Zones Index
    content = env.get_template("zone_index.md").render(zones=zones)
    with open(os.path.join(output_dir, "zones", "README.md"), "w", encoding="utf-8") as f:
        f.write(content)

    # Environments Index
    content = env.get_template("environment_index.md").render(environments=environments)
    with open(os.path.join(output_dir, "environments", "README.md"), "w", encoding="utf-8") as f:
        f.write(content)

    # Bridge Domains Index
    content = env.get_template("bridge_domain_index.md").render(bridge_domains=bridge_domains)
    with open(os.path.join(output_dir, "bridge_domains", "README.md"), "w", encoding="utf-8") as f:
        f.write(content)

    # EPGs Index
    content = env.get_template("epg_index.md").render(epgs=epgs)
    with open(os.path.join(output_dir, "epgs", "README.md"), "w", encoding="utf-8") as f:
        f.write(content)

    # Networks Index
    content = env.get_template("network_index.md").render(networks=sorted_networks)
    with open(os.path.join(output_dir, "networks", "README.md"), "w", encoding="utf-8") as f:
        f.write(content)
