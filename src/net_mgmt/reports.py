import ipaddress
import os
from typing import List

from .core import Network


def generate_markdown_report(networks: List[Network], output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    # Sort networks hierarchically: Datacenter -> Zone -> Bridge Domain -> Environment -> EPG -> Subnet
    # (ordered alphabetically by name)
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

    # 1. Network Overview -> README.md
    readme_path = os.path.join(output_dir, "README.md")
    with open(readme_path, "w") as f:
        f.write("# Network Overview\n")

        current_dc = None
        current_zone = None
        current_bd = None
        current_env = None
        current_epg = None

        first_iter = True
        in_table = False
        unassigned_header_written = False

        for network in sorted_networks:
            is_unassigned = not (
                network.datacenter or network.zone or network.bridge_domain or network.environment or network.epg
            )

            if is_unassigned:
                if in_table:
                    f.write("\n")
                    in_table = False

                if not unassigned_header_written:
                    unassigned_header_written = True
                    f.write("\n## 📂 Unassigned Networks\n\n")
                    f.write("| Name | CIDR | Context | VLAN | Description |\n")
                    f.write("| --- | --- | --- | --- | --- |\n")
                    in_table = True

                context = network.context or "default"
                vlan_str = str(network.vlan) if network.vlan is not None else "None"
                desc = network.description or ""
                f.write(f"| [{network.name}]({network.name}.md) | {network.cidr} | {context} | {vlan_str} | {desc} |\n")
            else:
                dc_val = network.datacenter or "unassigned"
                zone_val = network.zone or "unassigned"
                bd_val = network.bridge_domain or "unassigned"
                env_val = network.environment or "unassigned"
                epg_val = network.epg or "unassigned"

                # Check if any parent grouping level has changed
                dc_changed = first_iter or (dc_val != current_dc)
                zone_changed = dc_changed or (zone_val != current_zone)
                bd_changed = zone_changed or (bd_val != current_bd)
                env_changed = bd_changed or (env_val != current_env)
                epg_changed = env_changed or (epg_val != current_epg)

                first_iter = False

                if dc_changed or zone_changed or bd_changed or env_changed or epg_changed:
                    if in_table:
                        f.write("\n")
                        in_table = False

                    if dc_changed:
                        current_dc = dc_val
                        f.write(f"\n## 🏢 Datacenter: {current_dc}\n")

                    if zone_changed:
                        current_zone = zone_val
                        f.write(f"\n### 📍 Zone: {current_zone}\n")

                    if bd_changed:
                        current_bd = bd_val
                        f.write(f"\n#### 🌉 Bridge Domain: {current_bd}\n")

                    if env_changed:
                        current_env = env_val
                        f.write(f"\n##### 🌍 Environment: {current_env}\n")

                    if epg_changed:
                        current_epg = epg_val
                        f.write(f"\n###### 🏷️ EPG: {current_epg}\n")

                    # Start new flat table
                    f.write("\n| Name | CIDR | Context | VLAN | Description |\n")
                    f.write("| --- | --- | --- | --- | --- |\n")
                    in_table = True

                context = network.context or "default"
                vlan_str = str(network.vlan) if network.vlan is not None else "None"
                desc = network.description or ""

                f.write(f"| [{network.name}]({network.name}.md) | {network.cidr} | {context} | {vlan_str} | {desc} |\n")

    # 2. Detailed Network Information -> individual files
    for network in sorted_networks:
        net_path = os.path.join(output_dir, f"{network.name}.md")
        with open(net_path, "w") as f:
            f.write(f"# {network.name}\n\n")

            # Network Settings
            f.write("## Settings\n\n")
            f.write(f"- **CIDR**: `{network.cidr}`\n")
            f.write(f"- **Context**: `{network.context}`\n")
            if network.description:
                f.write(f"- **Description**: {network.description}\n")
            f.write(f"- **VLAN**: `{network.vlan}`\n")
            f.write(f"- **Bridge Domain**: `{network.bridge_domain}`\n")
            f.write(f"- **Environment**: `{network.environment}`\n")
            f.write(f"- **EPG**: `{network.epg}`\n")
            f.write(f"- **MTU**: `{network.default_mtu}`\n")

            dns_ns = ", ".join(network.dns_nameservers) if network.dns_nameservers else "None"
            f.write(f"- **DNS Nameservers**: `{dns_ns}`\n")

            dns_search = ", ".join(network.dns_search) if network.dns_search else "None"
            f.write(f"- **DNS Search**: `{dns_search}`\n")

            timeservers = ", ".join(network.timeservers) if network.timeservers else "None"
            f.write(f"- **Timeservers**: `{timeservers}`\n")

            if network.static_routes:
                routes_str = ", ".join([f"{sr.cidr} via {sr.gateway}" for sr in network.static_routes])
            else:
                routes_str = "None"
            f.write(f"- **Static Routes**: `{routes_str}`\n")

            f.write(f"- **Zone**: `{network.zone}`\n")
            f.write(f"- **Datacenter**: `{network.datacenter}`\n")
            f.write(f"- **Routable**: `{network.routable}`\n")
            f.write(f"- **Reserve Gateway**: `{network.reserve_gateway}`\n")
            f.write(f"- **Reserve Internal**: `{network.reserve_internal}`\n")

            # Reservations
            f.write("\n## Reservations\n\n")
            if network.effective_reservations:
                f.write("| ID | CIDR | Comment | Allocatable | Allocations | Usage |\n")
                f.write("| --- | --- | --- | --- | --- | --- |\n")
                # Sort reservations by IP
                sorted_res = sorted(network.effective_reservations, key=lambda r: r.networks[0].network_address)
                for res in sorted_res:
                    usage = network.get_reservation_usage(res.id)
                    usage_str = f"{usage['count']}/{usage['total']} ({usage['percent']:.1f}%)"
                    f.write(
                        f"| {res.id} | {res.cidr} | {res.comment} | {res.allocatable} "
                        f"| {usage['count']} | {usage_str} |\n"
                    )
            else:
                f.write("_No reservations._\n")

            # Allocations
            if network.allocations:
                f.write("\n## Allocations\n\n")
                f.write("| IP/CIDR | Hostname/Comment |\n")
                f.write("| --- | --- |\n")

                # Sort allocations
                def sort_key(a):
                    if a.ip:
                        return a.ip
                    try:
                        return ipaddress.ip_network(a.cidr.split("-")[0].strip(), strict=False).network_address
                    except ValueError:
                        return ipaddress.ip_address("0.0.0.0")

                sorted_allocs = sorted(network.allocations, key=sort_key)
                for alloc in sorted_allocs:
                    if alloc.ip:
                        f.write(f"| {alloc.ip} | {alloc.hostname} |\n")
                    else:
                        f.write(f"| {alloc.cidr} | {alloc.comment} |\n")

            # Unreserved Ranges
            unreserved = network.get_unreserved_display_ranges()
            if unreserved:
                f.write("\n## Unreserved Ranges\n\n")
                for rng in unreserved:
                    f.write(f"- `{rng}`\n")
