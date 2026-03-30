import ipaddress
from typing import List

from .core import Network


def generate_markdown_report(networks: List[Network], output_file: str):
    with open(output_file, "w") as f:
        # 1. Network Overview
        f.write("# Network Overview\n\n")

        f.write("| Name | CIDR | Context | VLAN | Bridge Domain | EPG | Zone | Datacenter | Description |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")

        for network in networks:
            desc = network.description or ""
            dc = network.datacenter or ""
            zone = network.zone or ""
            context = network.context or "default"
            f.write(
                f"| {network.name} | {network.cidr} | {context} | {network.vlan} | {network.bridge_domain} "
                f"| {network.epg} | {zone} | {dc} | {desc} |\n"
            )

        # 2. Detailed Network Information
        f.write("\n# Network Details\n")

        for network in networks:
            f.write(f"\n## {network.name}\n\n")

            # Network Settings
            f.write("### Settings\n\n")
            f.write(f"- **CIDR**: `{network.cidr}`\n")
            f.write(f"- **Context**: `{network.context}`\n")
            if network.description:
                f.write(f"- **Description**: {network.description}\n")
            f.write(f"- **VLAN**: `{network.vlan}`\n")
            f.write(f"- **Bridge Domain**: `{network.bridge_domain}`\n")
            f.write(f"- **EPG**: `{network.epg}`\n")
            f.write(f"- **Zone**: `{network.zone}`\n")
            f.write(f"- **Datacenter**: `{network.datacenter}`\n")
            f.write(f"- **Routable**: `{network.routable}`\n")
            f.write(f"- **Reserve Gateway**: `{network.reserve_gateway}`\n")
            f.write(f"- **Reserve Internal**: `{network.reserve_internal}`\n")

            # Reservations
            f.write("\n### Reservations\n\n")
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
                f.write("\n### Allocations\n\n")
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
            unreserved = network.get_unreserved_ranges()
            if unreserved:
                f.write("\n### Unreserved Ranges\n\n")
                for net in unreserved:
                    f.write(f"- `{net}`\n")
