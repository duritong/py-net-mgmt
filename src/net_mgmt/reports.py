import os
from typing import List, Optional

import jinja2

from .core import Network
from .db import get_cached_entities, set_db_path

# Resolve the absolute path of the bundled default templates directory
DEFAULT_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def build_overview_table_rows(
    sorted_networks: List[Network],
    datacenters: dict,
    zones: dict,
    bridge_domains: dict,
    epgs: dict,
) -> List[dict]:
    # 1. Identify aggregates and map them to their subnets
    aggregates = [n for n in sorted_networks if n.aggregate]
    aggregate_subnets = {}
    all_child_subnet_names = set()
    for agg in aggregates:
        subnets = sorted(agg.get_subnets(sorted_networks), key=lambda s: s.cidr)
        aggregate_subnets[agg.name] = subnets
        for s in subnets:
            all_child_subnet_names.add(s.name)

    # 2. Filter out purely unassigned networks (no DC, Zone, BD, EPG, aggregate, and not a child subnet)
    hierarchical_networks = []
    for net in sorted_networks:
        is_unassigned = (
            not (net.datacenter or net.zone or net.bridge_domain or net.environment or net.epg or net.aggregate)
            and net.name not in all_child_subnet_names
        )
        if not is_unassigned:
            hierarchical_networks.append(net)

    if not hierarchical_networks:
        return []

    # Helper for sorting keys: empty/None values sort last, then case-insensitive alphabetical
    def sort_key(val: Optional[str]):
        return (val is None or val == "", (val or "").lower())

    # Group hierarchical networks by Datacenter -> Zone
    dc_groups = {}
    for net in hierarchical_networks:
        dc_val = net.datacenter
        zone_val = net.zone
        dc_groups.setdefault(dc_val, {}).setdefault(zone_val, []).append(net)

    sorted_dcs = sorted(dc_groups.keys(), key=sort_key)
    rows = []

    for dc in sorted_dcs:
        zone_map = dc_groups[dc]

        defined_zones = [z for z in zone_map.keys() if z]
        defined_zones.sort(key=lambda z: z.lower())

        direct_dc_nets = []
        for z in [z for z in zone_map.keys() if not z]:
            for n in zone_map[z]:
                if not n.aggregate and n.name not in all_child_subnet_names:
                    direct_dc_nets.append(n)
        direct_dc_nets.sort(key=lambda n: n.name.lower())

        dc_level_aggs = []
        for z in [z for z in zone_map.keys() if not z]:
            for n in zone_map[z]:
                if n.aggregate:
                    dc_level_aggs.append(n)
        dc_level_aggs.sort(key=lambda a: a.name.lower())

        dc_items = []
        for z in defined_zones:
            dc_items.append(("zone", z, zone_map[z]))
        for agg in dc_level_aggs:
            dc_items.append(("aggregate", agg, aggregate_subnets.get(agg.name, [])))
        for net in direct_dc_nets:
            dc_items.append(("network", net, []))

        if dc:
            dc_label = f"🏢 **[{dc}](datacenters/{dc}.md)**" if dc in datacenters else f"🏢 **{dc}**"
        else:
            dc_label = "🏢 **unassigned**"

        rows.append({
            "label": dc_label,
            "cidr": "",
            "epg": "",
            "vlan": "",
            "context": "",
            "description": "",
        })

        for item_idx, (item_type, obj, item_nets) in enumerate(dc_items):
            is_last_dc_item = item_idx == len(dc_items) - 1
            dc_conn = "└── " if is_last_dc_item else "├── "
            dc_child_prefix = "    " if is_last_dc_item else "│   "

            if item_type == "zone":
                zone_name = obj
                zone_label = (
                    f"📍 **[{zone_name}](zones/{zone_name}.md)**" if zone_name in zones else f"📍 **{zone_name}**"
                )
                rows.append({
                    "label": f"{dc_conn}{zone_label}",
                    "cidr": "",
                    "epg": "",
                    "vlan": "",
                    "context": "",
                    "description": "",
                })

                zone_aggs = [n for n in item_nets if n.aggregate]
                zone_aggs.sort(key=lambda a: a.name.lower())

                zone_bds = {}
                zone_direct_nets = []
                for n in item_nets:
                    if n.aggregate:
                        continue
                    if n.name in all_child_subnet_names:
                        continue
                    if n.bridge_domain:
                        zone_bds.setdefault(n.bridge_domain, []).append(n)
                    else:
                        zone_direct_nets.append(n)

                sorted_bd_names = sorted(zone_bds.keys(), key=lambda b: b.lower())
                zone_direct_nets.sort(key=lambda n: n.name.lower())

                zone_items = []
                for agg in zone_aggs:
                    zone_items.append(("aggregate", agg, aggregate_subnets.get(agg.name, [])))
                for bd_name in sorted_bd_names:
                    zone_items.append(("bd", bd_name, sorted(zone_bds[bd_name], key=lambda n: n.name.lower())))
                for net in zone_direct_nets:
                    zone_items.append(("network", net, []))

                for z_idx, (z_type, z_obj, z_children) in enumerate(zone_items):
                    is_last_zi = z_idx == len(zone_items) - 1
                    zi_conn = "└── " if is_last_zi else "├── "
                    zi_child_prefix = dc_child_prefix + ("    " if is_last_zi else "│   ")

                    if z_type == "aggregate":
                        agg = z_obj
                        rows.append({
                            "label": f"{dc_child_prefix}{zi_conn}📦 [**{agg.name}**](networks/{agg.name}.md)",
                            "cidr": f"`{agg.cidr}`",
                            "epg": "*Aggregate*",
                            "vlan": "—",
                            "context": f"`{agg.context or 'default'}`",
                            "description": agg.description or "",
                        })
                        for sub_idx, sub in enumerate(z_children):
                            is_last_sub = sub_idx == len(z_children) - 1
                            sub_conn = "└── " if is_last_sub else "├── "
                            epg_str = (
                                f"[{sub.epg}](epgs/{sub.epg}.md)"
                                if (sub.epg and sub.epg in epgs)
                                else (sub.epg or "None")
                            )
                            vlan_str = str(sub.vlan) if sub.vlan is not None else "—"
                            rows.append({
                                "label": f"{zi_child_prefix}{sub_conn}🔌 [{sub.name}](networks/{sub.name}.md)",
                                "cidr": f"`{sub.cidr}`",
                                "epg": epg_str,
                                "vlan": vlan_str,
                                "context": f"`{sub.context or 'default'}`",
                                "description": sub.description or "",
                            })

                    elif z_type == "bd":
                        bd_name = z_obj
                        bd_label = (
                            f"🌉 **[{bd_name}](bridge_domains/{bd_name}.md)**"
                            if bd_name in bridge_domains
                            else f"🌉 **{bd_name}**"
                        )
                        rows.append({
                            "label": f"{dc_child_prefix}{zi_conn}{bd_label}",
                            "cidr": "",
                            "epg": "",
                            "vlan": "",
                            "context": "",
                            "description": "",
                        })
                        for net_idx, net in enumerate(z_children):
                            is_last_net = net_idx == len(z_children) - 1
                            net_conn = "└── " if is_last_net else "├── "
                            epg_str = (
                                f"[{net.epg}](epgs/{net.epg}.md)"
                                if (net.epg and net.epg in epgs)
                                else (net.epg or "None")
                            )
                            vlan_str = str(net.vlan) if net.vlan is not None else "—"
                            rows.append({
                                "label": f"{zi_child_prefix}{net_conn}🔌 [{net.name}](networks/{net.name}.md)",
                                "cidr": f"`{net.cidr}`",
                                "epg": epg_str,
                                "vlan": vlan_str,
                                "context": f"`{net.context or 'default'}`",
                                "description": net.description or "",
                            })

                    elif z_type == "network":
                        net = z_obj
                        epg_str = (
                            f"[{net.epg}](epgs/{net.epg}.md)"
                            if (net.epg and net.epg in epgs)
                            else (net.epg or "None")
                        )
                        vlan_str = str(net.vlan) if net.vlan is not None else "—"
                        rows.append({
                            "label": f"{dc_child_prefix}{zi_conn}🔌 [{net.name}](networks/{net.name}.md)",
                            "cidr": f"`{net.cidr}`",
                            "epg": epg_str,
                            "vlan": vlan_str,
                            "context": f"`{net.context or 'default'}`",
                            "description": net.description or "",
                        })

            elif item_type == "aggregate":
                agg = obj
                rows.append({
                    "label": f"{dc_conn}📦 [**{agg.name}**](networks/{agg.name}.md)",
                    "cidr": f"`{agg.cidr}`",
                    "epg": "*Aggregate*",
                    "vlan": "—",
                    "context": f"`{agg.context or 'default'}`",
                    "description": agg.description or "",
                })
                for sub_idx, sub in enumerate(item_nets):
                    is_last_sub = sub_idx == len(item_nets) - 1
                    sub_conn = "└── " if is_last_sub else "├── "
                    epg_str = (
                        f"[{sub.epg}](epgs/{sub.epg}.md)"
                        if (sub.epg and sub.epg in epgs)
                        else (sub.epg or "None")
                    )
                    vlan_str = str(sub.vlan) if sub.vlan is not None else "—"
                    rows.append({
                        "label": f"{dc_child_prefix}{sub_conn}🔌 [{sub.name}](networks/{sub.name}.md)",
                        "cidr": f"`{sub.cidr}`",
                        "epg": epg_str,
                        "vlan": vlan_str,
                        "context": f"`{sub.context or 'default'}`",
                        "description": sub.description or "",
                    })

            elif item_type == "network":
                net = obj
                epg_str = (
                    f"[{net.epg}](epgs/{net.epg}.md)"
                    if (net.epg and net.epg in epgs)
                    else (net.epg or "None")
                )
                vlan_str = str(net.vlan) if net.vlan is not None else "—"
                rows.append({
                    "label": f"{dc_conn}🔌 [{net.name}](networks/{net.name}.md)",
                    "cidr": f"`{net.cidr}`",
                    "epg": epg_str,
                    "vlan": vlan_str,
                    "context": f"`{net.context or 'default'}`",
                    "description": net.description or "",
                })

    return rows


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
    aggregate_networks = [n for n in sorted_networks if n.aggregate]
    for net in sorted_networks:
        content = env.get_template("network.md").render(network=net, all_networks=sorted_networks)
        with open(os.path.join(output_dir, "networks", f"{net.name}.md"), "w", encoding="utf-8") as f:
            f.write(content)

    # 6. Render Index (README.md) using Option B nested list structure
    tree = {}
    unassigned_networks = []

    for net in sorted_networks:
        if net.aggregate:
            continue
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

    rows = build_overview_table_rows(
        sorted_networks=sorted_networks,
        datacenters=datacenters,
        zones=zones,
        bridge_domains=bridge_domains,
        epgs=epgs,
    )

    content = env.get_template("index.md").render(
        tree=tree,
        unassigned_networks=unassigned_networks,
        aggregate_networks=aggregate_networks,
        all_networks=sorted_networks,
        rows=rows,
    )
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
