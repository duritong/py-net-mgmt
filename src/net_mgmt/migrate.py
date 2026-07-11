import os

import yaml

from .loader import load_all_networks, save_network_to_file


def run_migration(source_dir: str, output_dir: str):
    """
    Migrate a flat net-mgmt database at source_dir to a Relational Multi-Folder Database at output_dir.
    """
    if not os.path.exists(source_dir):
        raise ValueError(f"Source directory '{source_dir}' does not exist.")

    # 1. Load original flat database
    original_networks = load_all_networks(source_dir)

    # 2. Extract unique entities from hierarchy.yaml (if present)
    datacenters = {}
    zones = {}
    environments = {}
    bridge_domains = {}
    epgs = {}

    hierarchy_path = None
    for f in ["hierarchy.yaml", "hierarchy.yml"]:
        p = os.path.join(source_dir, f)
        if os.path.exists(p):
            hierarchy_path = p
            break

    if hierarchy_path:
        with open(hierarchy_path, "r", encoding="utf-8") as hf:
            try:
                config = yaml.safe_load(hf) or {}
            except Exception as e:
                raise ValueError(f"Failed to parse hierarchy file {hierarchy_path}: {e}")

        def traverse_hierarchy(node, dc_ctx=None, zone_ctx=None, bd_ctx=None, env_ctx=None):
            metadata_fields = ["timeservers", "dns_nameservers", "dns_search", "default_mtu"]

            if "datacenters" in node and node["datacenters"]:
                for dc_name, dc_node in node["datacenters"].items():
                    dc_props = {}
                    for field in metadata_fields:
                        if field in dc_node:
                            dc_props[field] = dc_node[field]
                    datacenters[dc_name] = dc_props
                    traverse_hierarchy(dc_node, dc_ctx=dc_name, zone_ctx=zone_ctx, bd_ctx=bd_ctx, env_ctx=env_ctx)

            if "zones" in node and node["zones"]:
                for zone_name, zone_node in node["zones"].items():
                    zone_props = {}
                    for field in metadata_fields:
                        if field in zone_node:
                            zone_props[field] = zone_node[field]
                    zones[zone_name] = zone_props
                    traverse_hierarchy(zone_node, dc_ctx=dc_ctx, zone_ctx=zone_name, bd_ctx=bd_ctx, env_ctx=env_ctx)

            if "bridge_domains" in node and node["bridge_domains"]:
                for bd_name, bd_node in node["bridge_domains"].items():
                    bd_props = {"datacenter": dc_ctx, "zone": zone_ctx}
                    for field in metadata_fields:
                        if field in bd_node:
                            bd_props[field] = bd_node[field]
                    bridge_domains[bd_name] = bd_props
                    traverse_hierarchy(bd_node, dc_ctx=dc_ctx, zone_ctx=zone_ctx, bd_ctx=bd_name, env_ctx=env_ctx)

            if "environments" in node and node["environments"]:
                for env_name, env_node in node["environments"].items():
                    env_props = {}
                    for field in metadata_fields:
                        if field in env_node:
                            env_props[field] = env_node[field]
                    environments[env_name] = env_props
                    traverse_hierarchy(env_node, dc_ctx=dc_ctx, zone_ctx=zone_ctx, bd_ctx=bd_ctx, env_ctx=env_name)

            if "epgs" in node and node["epgs"]:
                for epg_name, epg_node in node["epgs"].items():
                    epg_props = {"bridge_domain": bd_ctx, "environment": env_ctx}
                    if "vlan" in epg_node:
                        epg_props["vlan"] = epg_node["vlan"]
                    for field in metadata_fields:
                        if field in epg_node:
                            epg_props[field] = epg_node[field]
                    epgs[epg_name] = epg_props
                    traverse_hierarchy(epg_node, dc_ctx=dc_ctx, zone_ctx=zone_ctx, bd_ctx=bd_ctx, env_ctx=env_ctx)

        traverse_hierarchy(config)

    # 3. Extract unique entities defined locally on flat networks (to ensure complete coverage)
    for net in original_networks:
        if net.datacenter and net.datacenter not in datacenters:
            datacenters[net.datacenter] = {}
        if net.zone and net.zone not in zones:
            zones[net.zone] = {}
        if net.environment and net.environment not in environments:
            environments[net.environment] = {}
        if net.bridge_domain and net.bridge_domain not in bridge_domains:
            bridge_domains[net.bridge_domain] = {"datacenter": net.datacenter, "zone": net.zone}
        if net.epg:
            if net.epg not in epgs:
                epgs[net.epg] = {"bridge_domain": net.bridge_domain, "environment": net.environment, "vlan": net.vlan}
            else:
                if "vlan" not in epgs[net.epg] or epgs[net.epg]["vlan"] is None:
                    epgs[net.epg]["vlan"] = net.vlan

    # 4. Create target subfolders
    subdirs = ["datacenters", "zones", "environments", "bridge_domains", "epgs", "networks"]
    for subdir in subdirs:
        os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)

    # 5. Populate normalized configurations in subfolders
    def write_entity_file(subdir, name, data):
        # Clean any None values to keep YAML clean
        clean_data = {k: v for k, v in data.items() if v is not None}
        file_path = os.path.join(output_dir, subdir, f"{name}.yaml")
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(clean_data, f, sort_keys=False)

    for dc_name, dc_data in datacenters.items():
        write_entity_file("datacenters", dc_name, dc_data)
    for zone_name, zone_data in zones.items():
        write_entity_file("zones", zone_name, zone_data)
    for env_name, env_data in environments.items():
        write_entity_file("environments", env_name, env_data)
    for bd_name, bd_data in bridge_domains.items():
        write_entity_file("bridge_domains", bd_name, bd_data)
    for epg_name, epg_data in epgs.items():
        write_entity_file("epgs", epg_name, epg_data)

    # 6. Save pruned and updated network files under new layout
    for net in original_networks:
        orig_file_path = net.file_path
        net.file_path = os.path.join(output_dir, "networks", f"{net.name}.yaml")
        # Ensure any existing comments are NOT preserved in the output as per user's decision #4
        with open(net.file_path, "w") as f:
            f.write("")
        save_network_to_file(net)
        # Restore original path in-memory for safety verification
        net.file_path = orig_file_path

    # 7. Safety Verification
    migrated_networks = load_all_networks(output_dir)
    if len(original_networks) != len(migrated_networks):
        raise ValueError(
            f"Parity Error: Original database has {len(original_networks)} networks, "
            f"but migrated database has {len(migrated_networks)} networks."
        )

    orig_map = {n.name: n for n in original_networks}
    for migr_net in migrated_networks:
        if migr_net.name not in orig_map:
            raise ValueError(
                f"Parity Error: Network '{migr_net.name}' found in migrated database but not in original database."
            )
        orig_net = orig_map[migr_net.name]

        # Compare attributes
        attrs_to_compare = [
            "cidr",
            "vlan",
            "bridge_domain",
            "environment",
            "epg",
            "datacenter",
            "zone",
            "timeservers",
            "dns_nameservers",
            "dns_search",
            "default_mtu",
            "routable",
            "context",
        ]
        for attr in attrs_to_compare:
            orig_val = getattr(orig_net, attr)
            migr_val = getattr(migr_net, attr)
            if orig_val != migr_val:
                raise ValueError(
                    f"Parity Error for network '{migr_net.name}': "
                    f"Attribute '{attr}' differs. Original: {orig_val}, Migrated: {migr_val}"
                )

        # Compare reservations
        if len(orig_net.reservations) != len(migr_net.reservations):
            raise ValueError(
                f"Parity Error for network '{migr_net.name}': "
                f"Reservations count differs. Original: {len(orig_net.reservations)}, "
                f"Migrated: {len(migr_net.reservations)}"
            )
        for r_orig, r_migr in zip(orig_net.reservations, migr_net.reservations):
            if (
                r_orig.id != r_migr.id
                or str(r_orig.cidr) != str(r_migr.cidr)
                or r_orig.comment != r_migr.comment
                or r_orig.allocatable != r_migr.allocatable
            ):
                raise ValueError(f"Parity Error for network '{migr_net.name}': Reservation mismatch.")

        # Compare allocations
        if len(orig_net.allocations) != len(migr_net.allocations):
            raise ValueError(
                f"Parity Error for network '{migr_net.name}': "
                f"Allocations count differs. Original: {len(orig_net.allocations)}, "
                f"Migrated: {len(migr_net.allocations)}"
            )
        for a_orig, a_migr in zip(orig_net.allocations, migr_net.allocations):
            if (
                str(a_orig.ip) != str(a_migr.ip)
                or a_orig.hostname != a_migr.hostname
                or str(a_orig.cidr) != str(a_migr.cidr)
                or a_orig.comment != a_migr.comment
            ):
                raise ValueError(f"Parity Error for network '{migr_net.name}': Allocation mismatch.")
