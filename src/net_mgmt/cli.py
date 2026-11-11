import builtins
import ipaddress
import os
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .db import get_database, set_db_path

CONTEXT_SETTINGS = dict(max_content_width=120, terminal_width=120)


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """Network Management CLI"""
    pass


@cli.command()
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
@click.option("--format", is_flag=True, default=False, help="Format all database files if validation succeeds")
def validate(path, format):
    """Validate all networks"""
    set_db_path(path)
    try:
        networks = get_database(force_reload=True)
        click.echo(f"Successfully validated {len(networks)} networks.")
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    if format:
        run_format(path)


@cli.command()
@click.argument("level", type=str)
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
@click.option("--description", "-d", default=None, help="Filter networks by description (case-insensitive substring)")
@click.option("--cidr", default=None, help="Filter networks by CIDR (string or exact subnet)")
@click.option("--ip", default=None, help="Filter networks containing this IP address")
@click.option("--vlan", "-v", type=int, default=None, help="Filter networks by VLAN ID")
@click.option("--environment", "-e", default=None, help="Filter networks by Environment name")
@click.option("--datacenter", "--dc", default=None, help="Filter networks by Datacenter name")
@click.option("--zone", "-z", default=None, help="Filter networks by Zone name")
@click.option("--epg", default=None, help="Filter networks by EPG name")
@click.option("--bridge-domain", "--bd", default=None, help="Filter networks by Bridge Domain name")
@click.option("--context", "-c", default=None, help="Filter networks by Context name")
@click.option("--no-wrap", is_flag=True, default=False, help="Do not wrap or truncate text inside table columns")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "csv", "json"]),
    default="table",
    help="Output format (table, csv, json)",
)
@click.option("--sort-by", "--sort", default=None, help="Comma-separated list of fields to sort the output by")
@click.option(
    "--ip-version",
    type=click.Choice(["4", "6", "v4", "v6"]),
    default=None,
    help="Filter networks by IP version (4 or 6)",
)
def list(
    level,
    path,
    description,
    cidr,
    ip,
    vlan,
    environment,
    datacenter,
    zone,
    epg,
    bridge_domain,
    context,
    no_wrap,
    format,
    sort_by,
    ip_version,
):
    """List available networks or hierarchical level entities with coordinate filtering"""
    alias_map = {
        "networks": "networks",
        "network": "networks",
        "nets": "networks",
        "net": "networks",
        "bridge-domains": "bridge_domains",
        "bridge-domain": "bridge_domains",
        "bridgedomains": "bridge_domains",
        "bridgedomain": "bridge_domains",
        "bridge_domains": "bridge_domains",
        "bridge_domain": "bridge_domains",
        "bds": "bridge_domains",
        "bd": "bridge_domains",
        "datacenters": "datacenters",
        "datacenter": "datacenters",
        "dcs": "datacenters",
        "dc": "datacenters",
        "zones": "zones",
        "zone": "zones",
        "environments": "environments",
        "environment": "environments",
        "envs": "environments",
        "env": "environments",
        "epgs": "epgs",
        "epg": "epgs",
    }

    normalized_level = alias_map.get(level.lower())
    if not normalized_level:
        click.echo(f"Error: Unknown hierarchical level '{level}'.")
        exit(1)

    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    def sort_items(items, fields, is_dict=False):
        """Sort a list of items (objects or key-value tuples) based on a list of fields."""

        def get_val_for_field(item, field):
            f = field.strip().lower().replace("-", "_")
            if is_dict:
                name, data = item
                if f == "name":
                    return name
                val = data.get(f)
            else:
                if hasattr(item, f):
                    val = getattr(item, f)
                else:
                    val = None

            if val is None:
                val = ""

            # Check for CIDR or IP
            if f == "cidr":
                import ipaddress

                try:
                    net = ipaddress.ip_network(str(val), strict=False)
                    return (0, net.version, int(net.network_address), net.prefixlen)
                except Exception:
                    pass
            elif f in ["vlan", "default_mtu", "mtu"]:
                try:
                    return (0, int(val), "")
                except Exception:
                    return (1, 999999, str(val))

            return (2 if isinstance(val, int) else 3, str(val).lower())

        def sort_key(item):
            return tuple(get_val_for_field(item, f) for f in fields)

        return sorted(items, key=sort_key)

    sort_fields = []
    if sort_by:
        sort_fields = [f.strip() for f in sort_by.split(",") if f.strip()]

    if normalized_level != "networks":
        from .db import get_cached_entities

        entities = get_cached_entities(normalized_level)

        if not entities:
            click.echo(f"No {normalized_level.replace('_', ' ')} found.")
            return

        items = builtins.list(entities.items())
        if not sort_fields:
            if normalized_level == "bridge_domains":
                sort_fields = ["datacenter", "zone", "name"]
            elif normalized_level == "epgs":
                sort_fields = ["bridge_domain", "environment", "name"]
            else:
                sort_fields = ["name"]

        items = sort_items(items, sort_fields, is_dict=True)

        import sys

        no_wrap_effective = no_wrap or not sys.stdout.isatty()

        if format == "json":
            import json

            click.echo(json.dumps([{"name": k, **v} for k, v in items], indent=2))
            return

        # Determine headers & keys to display per level
        if normalized_level == "datacenters":
            headers = ["Name", "Timeservers", "DNS Nameservers"]
            keys = ["timeservers", "dns_nameservers"]
        elif normalized_level == "zones":
            headers = ["Name", "DNS Search"]
            keys = ["dns_search"]
        elif normalized_level == "environments":
            headers = ["Name", "Timeservers"]
            keys = ["timeservers"]
        elif normalized_level == "bridge_domains":
            headers = ["Name", "Datacenter", "Zone", "Default MTU"]
            keys = ["datacenter", "zone", "default_mtu"]
        elif normalized_level == "epgs":
            headers = ["Name", "Bridge Domain", "Environment", "VLAN", "Default MTU"]
            keys = ["bridge_domain", "environment", "vlan", "default_mtu"]

        if format == "csv":
            import csv

            writer = csv.writer(sys.stdout)
            writer.writerow(headers)
            for name, data in items:
                row = [name]
                for key in keys:
                    val = data.get(key, "")
                    if isinstance(val, builtins.list):
                        row.append(", ".join(map(str, val)))
                    else:
                        row.append(str(val) if val is not None else "")
                writer.writerow(row)
            return

        # Table format
        if no_wrap_effective:
            width = 9999
        else:
            width = None

        console = Console(width=width)
        table = Table()
        for h in headers:
            style = "cyan" if h == "Name" else "green" if "MTU" in h or "VLAN" in h else "magenta"
            table.add_column(h, style=style, no_wrap=no_wrap_effective)

        for name, data in items:
            row_vals = [name]
            for key in keys:
                val = data.get(key, "")
                if isinstance(val, builtins.list):
                    row_vals.append(", ".join(map(str, val)))
                else:
                    row_vals.append(str(val) if val is not None else "")
            table.add_row(*row_vals)

        console.print(table)
        return

    if not networks:
        click.echo("No networks found.")
        return

    # Symmetrical Filtering using Core query_networks
    from .core import query_networks as core_query_networks

    filters = {
        "description": description,
        "cidr": cidr,
        "ip": ip,
        "vlan": vlan,
        "environment": environment,
        "datacenter": datacenter,
        "zone": zone,
        "epg": epg,
        "bridge_domain": bridge_domain,
        "context": context,
        "ip_version": ip_version,
    }
    networks = core_query_networks(networks, filters=filters)

    if not networks:
        click.echo("No matching networks found.")
        return

    # Sort networks by hierarchy default or custom sort fields
    if not sort_fields:
        sort_fields = ["datacenter", "zone", "environment", "bridge_domain", "epg", "name", "cidr"]
    networks = sort_items(networks, sort_fields, is_dict=False)

    if format == "json":
        import json

        click.echo(json.dumps([n.to_dict for n in networks], indent=2))
        return

    if format == "csv":
        import csv
        import sys

        writer = csv.writer(sys.stdout)
        writer.writerow(["Name", "CIDR", "Context", "Datacenter", "Zone", "Environment", "MTU", "Description"])
        for net in networks:
            writer.writerow(
                [
                    net.name,
                    str(net.cidr),
                    net.context or "default",
                    net.datacenter or "",
                    net.zone or "",
                    net.environment or "",
                    str(net.default_mtu) if net.default_mtu is not None else "",
                    net.description or "",
                ]
            )
        return

    import sys

    no_wrap_effective = no_wrap or not sys.stdout.isatty()

    if no_wrap_effective:
        width = 9999
    else:
        width = None

    console = Console(width=width)
    table = Table()
    table.add_column("Name", style="cyan", no_wrap=no_wrap_effective)
    table.add_column("CIDR", style="green", no_wrap=no_wrap_effective)
    table.add_column("Context", style="magenta", no_wrap=no_wrap_effective)
    table.add_column("Datacenter", style="yellow", no_wrap=no_wrap_effective)
    table.add_column("Zone", style="blue", no_wrap=no_wrap_effective)
    table.add_column("Environment", style="white", no_wrap=no_wrap_effective)
    table.add_column("MTU", justify="right", no_wrap=no_wrap_effective)
    table.add_column("Description", no_wrap=no_wrap_effective)

    for net in networks:
        desc = net.description or ""
        dc = net.datacenter or ""
        zone = net.zone or ""
        context = net.context or "default"
        env = net.environment or ""
        mtu = str(net.default_mtu) if net.default_mtu is not None else ""
        table.add_row(net.name, str(net.cidr), context, dc, zone, env, mtu, desc)

    console.print(table)


def run_lookup(target: str, path: str = "networks", context: Optional[str] = None, format: str = "table"):
    """Perform IP/CIDR lookup and render output in specified format."""
    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    from .core import lookup_ip_or_cidr

    try:
        result = lookup_ip_or_cidr(target, networks, context=context)
    except ValueError as e:
        click.echo(f"Error: {e}")
        exit(1)

    target_type = result.get("target_type")
    if target_type == "ip":
        if not result.get("matches"):
            click.echo(f"Error: No network found containing IP '{target}'.")
            exit(1)
    elif target_type == "cidr":
        if result.get("match_type") == "none":
            click.echo(f"Error: No network found matching CIDR '{target}'.")
            exit(1)
        elif result.get("match_type") in ("exact", "subnet") and not result.get("matches"):
            click.echo(f"Error: No network found matching CIDR '{target}'.")
            exit(1)

    if format == "json":
        import json

        click.echo(json.dumps(result, indent=2))
        return

    if format == "csv":
        import csv
        import sys

        writer = csv.writer(sys.stdout)
        if target_type == "ip":
            writer.writerow(
                [
                    "Target",
                    "Type",
                    "Network",
                    "Network_CIDR",
                    "Context",
                    "Status",
                    "VLAN",
                    "Environment",
                    "Datacenter",
                    "Zone",
                    "Bridge_Domain",
                    "EPG",
                    "Default_Gateway",
                    "Allocation_Host",
                    "Allocation_Comment",
                    "Reservation_ID",
                    "Reservation_Comment",
                ]
            )
            for m in result.get("matches", []):
                alloc = m.get("allocation") or {}
                res = m.get("reservation") or {}
                writer.writerow(
                    [
                        result.get("target"),
                        "ip",
                        m.get("network"),
                        m.get("network_cidr"),
                        m.get("context") or "default",
                        m.get("status"),
                        str(m.get("vlan")) if m.get("vlan") is not None else "",
                        m.get("environment") or "",
                        m.get("datacenter") or "",
                        m.get("zone") or "",
                        m.get("bridge_domain") or "",
                        m.get("epg") or "",
                        m.get("gateway") or "",
                        alloc.get("hostname") or "",
                        alloc.get("comment") or "",
                        res.get("id") or "",
                        res.get("comment") or "",
                    ]
                )
        else:
            match_type = result.get("match_type")
            if match_type in ("exact", "subnet"):
                writer.writerow(
                    [
                        "Target",
                        "Type",
                        "Match_Type",
                        "Network",
                        "Network_CIDR",
                        "Context",
                        "Total_Addresses",
                        "VLAN",
                        "Environment",
                        "Datacenter",
                        "Zone",
                        "Bridge_Domain",
                        "EPG",
                        "Description",
                    ]
                )
                for m in result.get("matches", []):
                    writer.writerow(
                        [
                            result.get("target"),
                            "cidr",
                            match_type,
                            m.get("network"),
                            m.get("network_cidr"),
                            m.get("context") or "default",
                            m.get("num_addresses"),
                            str(m.get("vlan")) if m.get("vlan") is not None else "",
                            m.get("environment") or "",
                            m.get("datacenter") or "",
                            m.get("zone") or "",
                            m.get("bridge_domain") or "",
                            m.get("epg") or "",
                            m.get("description") or "",
                        ]
                    )
            elif match_type == "supernet":
                writer.writerow(
                    [
                        "Target",
                        "Type",
                        "Match_Type",
                        "Contained_Network",
                        "Contained_CIDR",
                        "Context",
                        "VLAN",
                        "Environment",
                        "Datacenter",
                        "Zone",
                        "Bridge_Domain",
                        "EPG",
                    ]
                )
                for net in result.get("contained_networks", []):
                    writer.writerow(
                        [
                            result.get("target"),
                            "cidr",
                            "supernet",
                            net.get("name"),
                            str(net.get("cidr")),
                            net.get("context") or "default",
                            str(net.get("vlan")) if net.get("vlan") is not None else "",
                            net.get("environment") or "",
                            net.get("datacenter") or "",
                            net.get("zone") or "",
                            net.get("bridge_domain") or "",
                            net.get("epg") or "",
                        ]
                    )
        return

    # Rich Table Console output
    import sys

    import rich.box

    width = 9999 if not sys.stdout.isatty() else None
    console = Console(width=width)

    if target_type == "ip":
        for i, match in enumerate(result.get("matches", [])):
            if i > 0:
                console.print("\n" + "=" * 50 + "\n")
            console.print(f"[bold cyan]Target:[/bold cyan] {result.get('target')} (IP Address)")
            console.print(f"[bold cyan]Network:[/bold cyan] {match.get('network')} ({match.get('network_cidr')})")
            console.print(f"[bold cyan]Context:[/bold cyan] {match.get('context') or 'default'}")

            status_raw = match.get("status", "unreserved")
            if status_raw == "allocated":
                styled_status = "[bold green]Allocated[/bold green]"
            elif status_raw == "available":
                styled_status = "[bold cyan]Available[/bold cyan]"
            elif status_raw == "reserved":
                styled_status = "[bold yellow]Reserved[/bold yellow]"
            else:
                styled_status = "[bold blue]Unreserved / Free[/bold blue]"
            console.print(f"[bold cyan]Status:[/bold cyan] {styled_status}")

            console.print(f"[bold cyan]Description:[/bold cyan] {match.get('description') or 'None'}")
            console.print(
                f"[bold cyan]VLAN:[/bold cyan] {match.get('vlan') if match.get('vlan') is not None else 'None'}"
            )
            console.print(f"[bold cyan]Bridge Domain:[/bold cyan] {match.get('bridge_domain') or 'None'}")
            console.print(f"[bold cyan]Environment:[/bold cyan] {match.get('environment') or 'None'}")
            console.print(f"[bold cyan]EPG:[/bold cyan] {match.get('epg') or 'None'}")
            console.print(f"[bold cyan]Zone:[/bold cyan] {match.get('zone') or 'None'}")
            console.print(f"[bold cyan]Datacenter:[/bold cyan] {match.get('datacenter') or 'None'}")
            console.print(f"[bold cyan]Default Gateway:[/bold cyan] {match.get('gateway') or 'None'}")
            mtu_str = match.get("default_mtu") if match.get("default_mtu") is not None else "None"
            console.print(f"[bold cyan]Default MTU:[/bold cyan] {mtu_str}")

            dns_ns = ", ".join(match.get("dns_nameservers", [])) if match.get("dns_nameservers") else "None"
            console.print(f"[bold cyan]DNS Nameservers:[/bold cyan] {dns_ns}")

            dns_search = ", ".join(match.get("dns_search", [])) if match.get("dns_search") else "None"
            console.print(f"[bold cyan]DNS Search:[/bold cyan] {dns_search}")

            timeservers = ", ".join(match.get("timeservers", [])) if match.get("timeservers") else "None"
            console.print(f"[bold cyan]Timeservers:[/bold cyan] {timeservers}")

            console.print(f"[bold cyan]Routable:[/bold cyan] {match.get('routable')}")
            if match.get("parent_aggregate"):
                console.print(f"[bold cyan]Parent Aggregate:[/bold cyan] {match.get('parent_aggregate')}")

            # Allocation details
            if match.get("allocation"):
                alloc = match["allocation"]
                console.print("\n[bold yellow]Allocation:[/bold yellow]")
                if alloc.get("hostname"):
                    console.print(f"  [bold cyan]Hostname:[/bold cyan] {alloc['hostname']}")
                if alloc.get("comment"):
                    console.print(f"  [bold cyan]Comment:[/bold cyan] {alloc['comment']}")
                alloc_type_desc = (
                    "Single IP" if alloc.get("type") == "single" else f"Subnet/Range ({alloc.get('cidr', '')})"
                )
                console.print(f"  [bold cyan]Type:[/bold cyan] {alloc_type_desc}")
            else:
                console.print("\n[bold yellow]Allocation:[/bold yellow] None")

            # Reservation details
            if match.get("reservation"):
                res = match["reservation"]
                console.print("\n[bold yellow]Reservation:[/bold yellow]")
                console.print(f"  [bold cyan]ID:[/bold cyan] {res.get('id')}")
                console.print(f"  [bold cyan]Definition:[/bold cyan] {res.get('cidr')}")
                console.print(f"  [bold cyan]Comment:[/bold cyan] {res.get('comment') or 'None'}")
                console.print(f"  [bold cyan]Allocatable:[/bold cyan] {res.get('allocatable', False)}")
            else:
                console.print("\n[bold yellow]Reservation:[/bold yellow] None (Unreserved range)")

    elif target_type == "cidr":
        match_type = result.get("match_type")
        if match_type in ("exact", "subnet"):
            for i, match in enumerate(result.get("matches", [])):
                if i > 0:
                    console.print("\n" + "=" * 50 + "\n")
                console.print(f"[bold cyan]Target:[/bold cyan] {result.get('target')} (CIDR Network)")
                match_desc = (
                    "Exact Network Match"
                    if match.get("is_exact_network")
                    else f"Subnet of Network {match.get('network')} ({match.get('network_cidr')})"
                )
                console.print(f"[bold cyan]Match Type:[/bold cyan] {match_desc}")
                console.print(f"[bold cyan]Network:[/bold cyan] {match.get('network')} ({match.get('network_cidr')})")
                console.print(f"[bold cyan]Context:[/bold cyan] {match.get('context') or 'default'}")
                console.print(f"[bold cyan]Total Addresses:[/bold cyan] {match.get('num_addresses')}")
                console.print(f"[bold cyan]Network Address:[/bold cyan] {match.get('network_address')}")
                if match.get("broadcast_address"):
                    console.print(f"[bold cyan]Broadcast Address:[/bold cyan] {match.get('broadcast_address')}")
                console.print(
                    f"[bold cyan]VLAN:[/bold cyan] {match.get('vlan') if match.get('vlan') is not None else 'None'}"
                )
                console.print(f"[bold cyan]Bridge Domain:[/bold cyan] {match.get('bridge_domain') or 'None'}")
                console.print(f"[bold cyan]Environment:[/bold cyan] {match.get('environment') or 'None'}")
                console.print(f"[bold cyan]EPG:[/bold cyan] {match.get('epg') or 'None'}")
                console.print(f"[bold cyan]Zone:[/bold cyan] {match.get('zone') or 'None'}")
                console.print(f"[bold cyan]Datacenter:[/bold cyan] {match.get('datacenter') or 'None'}")
                console.print(f"[bold cyan]Default Gateway:[/bold cyan] {match.get('gateway') or 'None'}")
                mtu_str = match.get("default_mtu") if match.get("default_mtu") is not None else "None"
                console.print(f"[bold cyan]Default MTU:[/bold cyan] {mtu_str}")
                dns_ns = ", ".join(match.get("dns_nameservers", [])) if match.get("dns_nameservers") else "None"
                console.print(f"[bold cyan]DNS Nameservers:[/bold cyan] {dns_ns}")
                dns_search = ", ".join(match.get("dns_search", [])) if match.get("dns_search") else "None"
                console.print(f"[bold cyan]DNS Search:[/bold cyan] {dns_search}")
                timeservers = ", ".join(match.get("timeservers", [])) if match.get("timeservers") else "None"
                console.print(f"[bold cyan]Timeservers:[/bold cyan] {timeservers}")
                console.print(f"[bold cyan]Description:[/bold cyan] {match.get('description') or 'None'}")
                console.print(f"[bold cyan]Routable:[/bold cyan] {match.get('routable')}")
                if match.get("parent_aggregate"):
                    console.print(f"[bold cyan]Parent Aggregate:[/bold cyan] {match.get('parent_aggregate')}")

                # Subnets if aggregate
                if match.get("subnets"):
                    console.print("\n[bold yellow]Sub-Prefixes (Subnets):[/bold yellow]")
                    sub_table = Table(box=rich.box.SIMPLE)
                    sub_table.add_column("Subnet", style="cyan")
                    sub_table.add_column("CIDR", style="green")
                    sub_table.add_column("EPG", style="magenta")
                    sub_table.add_column("VLAN", justify="right")
                    sub_table.add_column("Description")
                    for s in match["subnets"]:
                        sub_table.add_row(
                            s.get("name", ""),
                            str(s.get("cidr", "")),
                            s.get("epg") or "None",
                            str(s.get("vlan")) if s.get("vlan") is not None else "None",
                            s.get("description") or "",
                        )
                    console.print(sub_table)

                if match.get("unallocated_subnets"):
                    console.print("\n[bold yellow]Available Sub-Prefix Capacity:[/bold yellow]")
                    for b in match["unallocated_subnets"]:
                        console.print(f"  - [green]{b}[/green]")

                # Reservations
                if match.get("reservations"):
                    console.print("\n[bold yellow]Reservations:[/bold yellow]")
                    res_table = Table(box=rich.box.SIMPLE)
                    res_table.add_column("ID", style="cyan")
                    res_table.add_column("CIDR", style="green")
                    res_table.add_column("Comment")
                    res_table.add_column("Allocatable", justify="center")
                    for r in match["reservations"]:
                        res_table.add_row(
                            r.get("id", ""),
                            str(r.get("cidr", "")),
                            r.get("comment") or "",
                            str(r.get("allocatable", False)),
                        )
                    console.print(res_table)
                else:
                    console.print("\n[bold yellow]Reservations:[/bold yellow] None")

                # Allocations
                if match.get("allocations"):
                    console.print("\n[bold yellow]Allocations:[/bold yellow]")
                    alloc_table = Table(box=rich.box.SIMPLE)
                    alloc_table.add_column("IP/CIDR", style="green")
                    alloc_table.add_column("Hostname/Comment")
                    for a in match["allocations"]:
                        ident = a.get("hostname") or a.get("comment") or ""
                        addr = a.get("ip") or a.get("cidr") or ""
                        alloc_table.add_row(str(addr), ident)
                    console.print(alloc_table)
                else:
                    console.print("\n[bold yellow]Allocations:[/bold yellow] None")

                # Unreserved
                if match.get("unreserved_ranges"):
                    console.print("\n[bold yellow]Unreserved Ranges:[/bold yellow]")
                    for rng in match["unreserved_ranges"]:
                        console.print(f"  [green]{rng}[/green]")

        elif match_type == "supernet":
            console.print(f"[bold cyan]Target:[/bold cyan] {result.get('target')} (CIDR Supernet)")
            count = len(result.get("contained_networks", []))
            console.print(f"[bold cyan]Match Type:[/bold cyan] Supernet Containing {count} Network(s)")
            console.print(f"[bold cyan]Total Capacity:[/bold cyan] {result.get('total_addresses')} addresses")
            console.print("\n[bold yellow]Contained Networks:[/bold yellow]")
            table = Table(box=rich.box.SIMPLE)
            table.add_column("Name", style="cyan")
            table.add_column("CIDR", style="green")
            table.add_column("Context")
            table.add_column("VLAN", justify="right")
            table.add_column("Environment")
            table.add_column("Datacenter")
            table.add_column("Zone")
            table.add_column("Bridge Domain")
            table.add_column("EPG")
            table.add_column("Description")
            for n in result.get("contained_networks", []):
                table.add_row(
                    n.get("name", ""),
                    str(n.get("cidr", "")),
                    n.get("context") or "default",
                    str(n.get("vlan")) if n.get("vlan") is not None else "None",
                    n.get("environment") or "",
                    n.get("datacenter") or "",
                    n.get("zone") or "",
                    n.get("bridge_domain") or "",
                    n.get("epg") or "",
                    n.get("description") or "",
                )
            console.print(table)


@cli.command()
@click.argument("level", type=str)
@click.argument("name", type=str)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "csv", "json"]),
    default="table",
    help="Output format (table, csv, json)",
)
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
@click.option("--context", "-c", default=None, help="Filter by network context")
def show(level, name, format, path, context=None):
    """Show details of a specific network or hierarchical entity"""
    alias_map = {
        "networks": "networks",
        "network": "networks",
        "nets": "networks",
        "net": "networks",
        "bridge-domains": "bridge_domains",
        "bridge-domain": "bridge_domains",
        "bridgedomains": "bridge_domains",
        "bridgedomain": "bridge_domains",
        "bridge_domains": "bridge_domains",
        "bridge_domain": "bridge_domains",
        "bds": "bridge_domains",
        "bd": "bridge_domains",
        "datacenters": "datacenters",
        "datacenter": "datacenters",
        "dcs": "datacenters",
        "dc": "datacenters",
        "zones": "zones",
        "zone": "zones",
        "environments": "environments",
        "environment": "environments",
        "envs": "environments",
        "env": "environments",
        "epgs": "epgs",
        "epg": "epgs",
        "ip": "ip",
        "cidr": "cidr",
    }
    normalized_level = alias_map.get(level.lower())
    if not normalized_level:
        click.echo(f"Error: Unknown hierarchical level '{level}'.")
        exit(1)

    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    if normalized_level in ("ip", "cidr"):
        run_lookup(name, path=path, context=context, format=format)
        return

    if normalized_level != "networks":
        from .db import get_cached_entities

        entities = get_cached_entities(normalized_level)

        # Case-insensitive lookup of entity name
        entity_key = next((k for k in entities if k.lower() == name.lower()), None)
        if not entity_key:
            level_label = level.rstrip("s")
            click.echo(f"Error: {level_label.capitalize()} '{name}' not found.")
            exit(1)

        entity_data = entities[entity_key]

        if format == "json":
            import json

            click.echo(json.dumps({"name": entity_key, **entity_data}, indent=2))
            return

        if format == "csv":
            import csv
            import sys

            writer = csv.writer(sys.stdout)
            writer.writerow(["Key", "Value"])
            writer.writerow(["name", entity_key])
            for k, v in sorted(entity_data.items()):
                if isinstance(v, builtins.list):
                    writer.writerow([k, ", ".join(map(str, v))])
                else:
                    writer.writerow([k, str(v) if v is not None else ""])
            return

        import sys

        width = 9999 if not sys.stdout.isatty() else None
        console = Console(width=width)
        console.print(f"[bold cyan]Name:[/bold cyan] {entity_key}")
        for k, v in sorted(entity_data.items()):
            label = " ".join(part.capitalize() for part in k.split("_"))
            if label == "Dns Nameservers":
                label = "DNS Nameservers"
            elif label == "Dns Search":
                label = "DNS Search"
            elif label == "Mtu":
                label = "MTU"
            elif label == "Vlan":
                label = "VLAN"
            elif label == "Epg":
                label = "EPG"

            if isinstance(v, builtins.list):
                val_str = ", ".join(map(str, v))
            else:
                val_str = str(v) if v is not None else "None"
            console.print(f"[bold cyan]{label}:[/bold cyan] {val_str}")
        return

    network = next((n for n in networks if n.name == name), None)

    if not network:
        click.echo(f"Network '{name}' not found.")
        return

    if format == "json":
        import json

        click.echo(json.dumps(network.to_dict, indent=2))
        return

    if format == "csv":
        import csv
        import sys

        writer = csv.writer(sys.stdout)
        writer.writerow(["Type", "ID_Hostname", "CIDR_IP", "Comment", "Allocatable"])
        # Reservations
        for res in network.effective_reservations:
            writer.writerow(
                ["reservation", res.id, str(res.cidr), res.comment or "", "True" if res.allocatable else "False"]
            )
        # Allocations
        for alloc in network.allocations:
            writer.writerow(["allocation", alloc.hostname or "", str(alloc.ip or alloc.cidr), alloc.comment or "", ""])
        return

    import sys

    import rich.box

    width = 9999 if not sys.stdout.isatty() else None
    console = Console(width=width)

    console.print(f"[bold cyan]Name:[/bold cyan] {network.name}")
    console.print(f"[bold cyan]CIDR:[/bold cyan] {network.cidr}")
    console.print(f"[bold cyan]Context:[/bold cyan] {network.context}")
    console.print(f"[bold cyan]Description:[/bold cyan] {network.description or 'None'}")
    console.print(f"[bold cyan]VLAN:[/bold cyan] {network.vlan}")
    console.print(f"[bold cyan]Bridge Domain:[/bold cyan] {network.bridge_domain or 'None'}")
    console.print(f"[bold cyan]Environment:[/bold cyan] {network.environment or 'None'}")
    console.print(f"[bold cyan]EPG:[/bold cyan] {network.epg or 'None'}")
    console.print(f"[bold cyan]Default MTU:[/bold cyan] {network.default_mtu}")

    dns_ns = ", ".join(network.dns_nameservers) if network.dns_nameservers else "None"
    console.print(f"[bold cyan]DNS Nameservers:[/bold cyan] {dns_ns}")

    dns_search = ", ".join(network.dns_search) if network.dns_search else "None"
    console.print(f"[bold cyan]DNS Search:[/bold cyan] {dns_search}")

    timeservers = ", ".join(network.timeservers) if network.timeservers else "None"
    console.print(f"[bold cyan]Timeservers:[/bold cyan] {timeservers}")

    if network.static_routes:
        routes_str = ", ".join([f"{sr.cidr} via {sr.gateway}" for sr in network.static_routes])
    else:
        routes_str = "None"
    console.print(f"[bold cyan]Static Routes:[/bold cyan] {routes_str}")

    console.print(f"[bold cyan]Zone:[/bold cyan] {network.zone or 'None'}")
    console.print(f"[bold cyan]Datacenter:[/bold cyan] {network.datacenter or 'None'}")
    console.print(f"[bold cyan]Routable:[/bold cyan] {network.routable}")
    if network.aggregate:
        console.print("[bold cyan]Aggregate Network:[/bold cyan] True")
    console.print(f"[bold cyan]Reserve Gateway:[/bold cyan] {network.reserve_gateway}")
    console.print(f"[bold cyan]Reserve Internal:[/bold cyan] {network.reserve_internal}")
    console.print(f"[bold cyan]Reserve Internal Until:[/bold cyan] {network.reserve_internal_until}")

    all_nets = get_database()
    if network.aggregate:
        subnets = network.get_subnets(all_nets)
        if subnets:
            console.print("\n[bold yellow]Sub-Prefixes (Subnets):[/bold yellow]")
            sub_table = Table(box=rich.box.SIMPLE)
            sub_table.add_column("Subnet", style="cyan")
            sub_table.add_column("CIDR", style="green")
            sub_table.add_column("EPG", style="magenta")
            sub_table.add_column("VLAN", justify="right")
            sub_table.add_column("Description")
            for sub in sorted(subnets, key=lambda s: s.cidr):
                sub_table.add_row(
                    sub.name,
                    str(sub.cidr),
                    sub.epg or "None",
                    str(sub.vlan) if sub.vlan is not None else "None",
                    sub.description or "",
                )
            console.print(sub_table)
        unallocated = network.get_unallocated_subnets(all_nets)
        if unallocated:
            console.print("\n[bold yellow]Available Sub-Prefix Capacity:[/bold yellow]")
            for block in unallocated:
                console.print(f"  - [green]{block}[/green]")
    else:
        parent = network.get_parent_aggregate(all_nets)
        if parent:
            console.print(f"[bold cyan]Parent Aggregate:[/bold cyan] {parent.name} ({parent.cidr})")

    if network.effective_reservations:
        console.print("\n[bold yellow]Reservations:[/bold yellow]")
        table = Table(box=rich.box.SIMPLE)
        table.add_column("ID", style="cyan")
        table.add_column("CIDR", style="green")
        table.add_column("Comment")
        table.add_column("Allocatable", justify="center")
        table.add_column("Allocations", justify="right")
        table.add_column("Usage", justify="right")

        # Sort reservations by their starting IP address
        sorted_reservations = sorted(
            network.effective_reservations,
            key=lambda r: (r.networks[0].network_address, str(r.cidr), str(r.id)),
        )
        for res in sorted_reservations:
            usage = network.get_reservation_usage(res.id, res.cidr)
            alloc_count = str(usage["count"])
            usage_pct = f"{usage['percent']:.1f}%"
            table.add_row(
                res.id,
                str(res.cidr),
                res.comment,
                str(res.allocatable),
                alloc_count,
                usage_pct,
            )
        console.print(table)
    else:
        console.print("\n[bold yellow]Reservations:[/bold yellow] None")

    if network.allocations:
        console.print("\n[bold yellow]Allocations:[/bold yellow]")
        table = Table(box=rich.box.SIMPLE)
        table.add_column("IP/CIDR", style="green")
        table.add_column("Hostname/Comment")

        # Sort allocations
        def sort_key(a):
            if a.ip:
                return (0, a.ip.version, int(a.ip))
            try:
                addr = ipaddress.ip_network(a.cidr.split("-")[0].strip(), strict=False).network_address
                return (1, addr.version, int(addr))
            except ValueError:
                return (2, 0, str(a.cidr))

        sorted_allocations = sorted(network.allocations, key=sort_key)
        for alloc in sorted_allocations:
            if alloc.ip:
                table.add_row(str(alloc.ip), alloc.hostname)
            else:
                table.add_row(alloc.cidr, alloc.comment)
        console.print(table)

    # Show unreserved ranges
    unreserved = network.get_unreserved_display_ranges()
    if unreserved:
        console.print("\n[bold yellow]Unreserved Ranges:[/bold yellow]")
        for rng in unreserved:
            console.print(f"  [green]{rng}[/green]")


@cli.command("lookup")
@click.argument("target", type=str)
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
@click.option("--context", "-c", default=None, help="Filter lookup to a specific network context")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "csv", "json"]),
    default="table",
    help="Output format (table, csv, json)",
)
def lookup(target, path, context, format):
    """Lookup an IP address or CIDR network and display containing network, status, and reservations"""
    run_lookup(target, path=path, context=context, format=format)


@cli.command()
@click.argument("name")
@click.option("--reservation", help="Reservation ID to allocate from")
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
def get_next_ip(name, reservation, path):
    """Get next free IP from a network"""
    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    network = next((n for n in networks if n.name == name), None)

    if not network:
        click.echo(f"Network '{name}' not found.")
        return

    try:
        ip = network.get_next_free_ip(reservation)
        click.echo(str(ip))
    except ValueError as e:
        click.echo(f"Error: {e}")
        exit(1)


@cli.command()
@click.argument("network_name")
@click.option("--ip", help="IP address for single allocation")
@click.option("--hostname", help="Hostname for single allocation")
@click.option("--cidr", help="CIDR or range for subnet allocation")
@click.option("--comment", help="Comment for allocation")
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
def add_allocation(network_name, ip, hostname, cidr, comment, path):
    """Add a new allocation (single IP or subnet/range) to a network"""
    from .core import Allocation

    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    network = next((n for n in networks if n.name == network_name), None)

    if not network:
        click.echo(f"Network '{network_name}' not found.")
        exit(1)

    try:
        if ip:
            if cidr:
                click.echo("Error: Cannot specify both --ip and --cidr")
                exit(1)
            new_alloc = Allocation(ip=ip, hostname=hostname, comment=comment)
        elif cidr:
            new_alloc = Allocation(cidr=cidr, comment=comment)
        else:
            click.echo("Error: Must specify either --ip or --cidr")
            exit(1)

        network.add_allocation(new_alloc)
        target = ip if ip else cidr
        desc = hostname if hostname else comment
        click.echo(f"Successfully added allocation {target} ({desc}) to network {network_name}")
    except ValueError as e:
        click.echo(f"Error adding allocation: {e}")
        exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}")
        exit(1)


@cli.command()
@click.argument("network_name")
@click.option("--ip", help="IP address to delete")
@click.option("--hostname", help="Hostname to delete")
@click.option("--cidr", help="CIDR or range to delete")
@click.option("--comment", help="Comment to delete")
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
def delete_allocation(network_name, ip, hostname, cidr, comment, path):
    """Delete allocations matching the given criteria."""
    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    network = next((n for n in networks if n.name == network_name), None)

    if not network:
        click.echo(f"Network '{network_name}' not found.")
        exit(1)

    if not any([ip, hostname, cidr, comment]):
        click.echo("Error: Must specify at least one of --ip, --hostname, --cidr, --comment")
        exit(1)

    try:
        deleted_count = network.delete_allocations(ip=ip, hostname=hostname, comment=comment, cidr=cidr)
        if deleted_count > 0:
            click.echo(f"Successfully deleted {deleted_count} allocation(s) from network {network_name}")
        else:
            click.echo("No matching allocations found to delete.")
    except Exception as e:
        click.echo(f"Error deleting allocation: {e}")
        exit(1)


@cli.command()
@click.argument("network_name")
@click.argument("hostname")
@click.option("--reservation-id", help="Optional reservation ID to allocate from")
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
def find_or_allocate_hostname(network_name, hostname, reservation_id, path):
    """Find or allocate a single IP by hostname in a network."""
    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    network = next((n for n in networks if n.name == network_name), None)

    if not network:
        click.echo(f"Network '{network_name}' not found.")
        exit(1)

    try:
        alloc = network.find_or_allocate_hostname(hostname, reservation_id)
        click.echo(f"{alloc.ip}")
    except ValueError as e:
        click.echo(f"Error: {e}")
        exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}")
        exit(1)


@cli.command()
@click.argument("network_name")
@click.argument("comment")
@click.argument("count", type=int)
@click.option("--reservation-id", help="Optional reservation ID to allocate from")
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
def find_or_allocate_range(network_name, comment, count, reservation_id, path):
    """Find or allocate a range of IPs by comment in a network."""
    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    network = next((n for n in networks if n.name == network_name), None)

    if not network:
        click.echo(f"Network '{network_name}' not found.")
        exit(1)

    try:
        allocs = network.find_or_allocate_range(comment, count, reservation_id)
        for alloc in allocs:
            if alloc.cidr:
                click.echo(f"{alloc.cidr}")
            else:
                click.echo(f"{alloc.ip}")
    except ValueError as e:
        click.echo(f"Error: {e}")
        exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}")
        exit(1)


@cli.command("get-vlans")
@click.option("--environment", "-env", help="Filter by Environment")
@click.option("--zone", "-z", help="Filter by Zone")
@click.option("--datacenter", "-dc", help="Filter by Datacenter")
@click.option("--bridge-domain", "-bd", help="Filter by Bridge Domain")
@click.option("--epg", help="Filter by EPG")
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
def get_vlans(environment, zone, datacenter, bridge_domain, epg, path):
    """Query unique VLAN IDs matching hierarchical filters"""
    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    from .core import query_vlans

    vlans = query_vlans(
        networks,
        environment=environment,
        zone=zone,
        datacenter=datacenter,
        bridge_domain=bridge_domain,
        epg=epg,
    )

    if not vlans:
        click.echo("No matching VLANs found.")
    else:
        for vlan in vlans:
            click.echo(vlan)


@cli.command()
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
@click.option("--output", "-o", default="generated-docs", help="Output directory for markdown files")
@click.option("--templates", "-t", default=None, help="Directory containing custom Jinja2 template overrides")
def generate_markdown(path, output, templates):
    """Generate markdown overview in an output directory"""
    from .reports import generate_markdown_report

    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    generate_markdown_report(networks, output, templates_dir=templates)
    click.echo(f"Markdown reports generated in {output}")


@cli.command("apply-template")
@click.option("--template", "-t", required=True, help="Path to the YAML reservation template file (REQUIRED)")
@click.option("--network", "-n", default=None, help="Name of specific network to apply (applies globally if omitted)")
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
def apply_template(template, network, path):
    """Apply relative reservation template to matching networks"""
    import yaml

    if not os.path.exists(template):
        click.echo(f"Error: Template file '{template}' not found.")
        exit(1)

    try:
        with open(template, "r", encoding="utf-8") as f:
            template_data = yaml.safe_load(f) or {}
    except Exception as e:
        click.echo(f"Error: Failed to parse template YAML file: {e}")
        exit(1)

    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    target_networks = []
    if network:
        net = next((n for n in networks if n.name == network), None)
        if not net:
            click.echo(f"Error: Network '{network}' not found.")
            exit(1)
        target_networks.append(net)
    else:
        req_len = template_data.get("required_prefix_len") or template_data.get("required_prefix_length")
        if req_len is not None:
            target_networks = [n for n in networks if n.cidr.prefixlen == int(req_len)]
            if not target_networks:
                click.echo(f"No networks found matching template prefix length /{req_len}.")
                return
        else:
            target_networks = networks

    click.echo(f"Applying template '{template}' to {len(target_networks)} target network(s)...")

    import sys

    console = Console(file=sys.stdout)
    for net in target_networks:
        try:
            res = net.apply_reservation_template(template_data)
            console.print(f"\nNetwork: [bold cyan]{net.name}[/bold cyan] ({net.cidr})")
            if res["applied"]:
                console.print(f"  [bold green]Applied:[/bold green] {', '.join(res['applied'])}")
            if res["skipped"]:
                console.print(f"  [bold yellow]Skipped (Idempotent):[/bold yellow] {', '.join(res['skipped'])}")
            if res["failed"]:
                console.print("  [bold red]Failed:[/bold red]")
                for rid, err in res["failed"].items():
                    console.print(f"    - {rid}: [red]{err}[/red]")
        except ValueError as e:
            console.print(f"\nNetwork: [bold cyan]{net.name}[/bold cyan] ({net.cidr})")
            console.print(f"  [bold red]Error:[/bold red] [red]{e}[/red]")


@cli.command()
@click.argument("entity_type")
@click.argument("name")
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
def edit(entity_type, name, path):
    """Open the respective database file inside $EDITOR"""
    import subprocess

    alias_map = {
        "networks": "networks",
        "network": "networks",
        "nets": "networks",
        "net": "networks",
        "bridge-domains": "bridge_domains",
        "bridge-domain": "bridge_domains",
        "bridgedomains": "bridge_domains",
        "bridgedomain": "bridge_domains",
        "bridge_domains": "bridge_domains",
        "bridge_domain": "bridge_domains",
        "bds": "bridge_domains",
        "bd": "bridge_domains",
        "datacenters": "datacenters",
        "datacenter": "datacenters",
        "dcs": "datacenters",
        "dc": "datacenters",
        "zones": "zones",
        "zone": "zones",
        "environments": "environments",
        "environment": "environments",
        "envs": "environments",
        "env": "environments",
        "epgs": "epgs",
        "epg": "epgs",
    }

    normalized_type = alias_map.get(entity_type.lower())
    if not normalized_type:
        click.echo(f"Error: Unknown entity type '{entity_type}'.")
        exit(1)

    file_path = None

    # Check standard relational subdirectory folder
    possible_extensions = [".yaml", ".yml"]
    for ext in possible_extensions:
        p = os.path.join(path, normalized_type, f"{name}{ext}")
        if os.path.exists(p):
            file_path = p
            break
    if not file_path:
        # Fallback to suggestion
        file_path = os.path.join(path, normalized_type, f"{name}.yaml")

    # Scaffold the directory if missing
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # 1. Read and backup the original content (if it exists)
    original_exists = os.path.exists(file_path)
    original_content = None
    if original_exists:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original_content = f.read()
        except Exception:
            pass

    # Resolve active editor from environment with safe terminal fallback
    editor = os.environ.get("EDITOR", "vi")

    # 2. Launch the editor
    click.echo(f"Opening '{file_path}' in editor '{editor}'...")
    try:
        subprocess.run([editor, file_path], check=True)
    except Exception as e:
        click.echo(f"Error: Failed to launch editor '{editor}': {e}")
        exit(1)

    # 3. Validation & Format Verification
    set_db_path(path)
    validation_failed = False
    validation_error = None
    try:
        get_database(force_reload=True)
    except Exception as e:
        validation_failed = True
        validation_error = e

    if validation_failed:
        # Read the invalid edited content
        invalid_content = ""
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    invalid_content = f.read()
        except Exception:
            pass

        # Write to a temporary recovery file
        import tempfile

        try:
            fd, recovery_path = tempfile.mkstemp(prefix=f"net-mgmt-recovery-{name}-", suffix=".yaml")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(invalid_content)
        except Exception as tmp_err:
            recovery_path = f"Failed to save recovery file: {tmp_err}"

        # Restore original state
        try:
            if original_exists:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(original_content)
                click.echo("Rejected invalid changes. Restored original file content.")
            else:
                if os.path.exists(file_path):
                    os.remove(file_path)
                click.echo("Rejected invalid changes. Removed newly created file.")
        except Exception as restore_err:
            click.echo(f"Warning: Failed to restore original file state: {restore_err}")

        # Print detailed validation error using rich Console
        console = Console()
        console.print(f"\n[bold red]Validation Error:[/bold red] {validation_error}")
        console.print(f"Your modified content was rejected and saved to: [yellow]{recovery_path}[/yellow]")
        exit(1)

    # 4. If validated, apply proper formatting to the database files!
    try:
        run_format(path)
        click.echo("Successfully validated and formatted the edited file.")
    except Exception as fmt_err:
        click.echo(f"Warning: Failed to format files: {fmt_err}")


def run_format(path):
    """Format and order all keys, reservations, and allocations in database files."""
    import io

    from .loader import format_yaml_node, get_yaml_handler

    yaml_rt = get_yaml_handler()

    # Walk directory and load files
    files_to_format = []
    for root, _, files in os.walk(path):
        for file in files:
            if file.lower().endswith((".yaml", ".yml")):
                files_to_format.append(os.path.join(root, file))

    if not files_to_format:
        click.echo("No YAML files found to format.")
        return

    formatted_count = 0
    skipped_count = 0

    for file_path in files_to_format:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content_before = f.read()

            # Round-trip load
            data = yaml_rt.load(content_before)
            if data is None:
                continue

            # Format
            formatted_data = format_yaml_node(data)

            # Dump to buffer to check changes
            buf = io.StringIO()
            yaml_rt.dump(formatted_data, buf)
            content_after = buf.getvalue()

            if content_before == content_after:
                skipped_count += 1
                continue

            # Save back to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content_after)
            formatted_count += 1
        except Exception as e:
            click.echo(f"Error: Failed to format file '{file_path}': {e}")

    click.echo(f"Format complete. Formatted: {formatted_count} file(s), Skipped: {skipped_count} file(s).")


@cli.command("format")
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
def format_cmd(path):
    """Format and order all keys, reservations, and allocations in database files"""
    if not os.path.exists(path):
        click.echo(f"Error: Database path '{path}' does not exist.")
        exit(1)

    # Safety Check: First ensure the database fully validates!
    set_db_path(path)
    try:
        get_database(force_reload=True)
    except ValueError as e:
        click.echo(f"Format Error: Cannot format because database contains validation errors: {e}")
        exit(1)

    # If it validates, proceed with formatting!
    run_format(path)


@cli.command("completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]), default="bash", required=False)
def completion_cmd(shell):
    """Output shell completion script for bash, zsh, or fish"""
    from click.shell_completion import get_completion_class

    comp_cls = get_completion_class(shell)
    if comp_cls:
        comp = comp_cls(cli, {}, "net-mgmt", "_NET_MGMT_COMPLETE")
        click.echo(comp.source().rstrip())


def main():
    cli()


if __name__ == "__main__":
    main()
