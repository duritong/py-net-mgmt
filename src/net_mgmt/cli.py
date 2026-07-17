import ipaddress
import os

import click
from rich.console import Console
from rich.table import Table

from .db import get_database, set_db_path


@click.group()
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
def list(
    path, description, cidr, ip, vlan, environment, datacenter, zone, epg, bridge_domain, context, no_wrap, format
):
    """List available networks with coordinate filtering"""
    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

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
    }
    networks = core_query_networks(networks, filters=filters)

    if not networks:
        click.echo("No matching networks found.")
        return

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

    if no_wrap:
        width = 9999
    elif not sys.stdout.isatty():
        width = 120
    else:
        width = None

    console = Console(width=width)
    table = Table()
    table.add_column("Name", style="cyan", no_wrap=no_wrap)
    table.add_column("CIDR", style="green", no_wrap=no_wrap)
    table.add_column("Context", style="magenta", no_wrap=no_wrap)
    table.add_column("Datacenter", style="yellow", no_wrap=no_wrap)
    table.add_column("Zone", style="blue", no_wrap=no_wrap)
    table.add_column("Environment", style="white", no_wrap=no_wrap)
    table.add_column("MTU", justify="right", no_wrap=no_wrap)
    table.add_column("Description", no_wrap=no_wrap)

    for net in networks:
        desc = net.description or ""
        dc = net.datacenter or ""
        zone = net.zone or ""
        context = net.context or "default"
        env = net.environment or ""
        mtu = str(net.default_mtu) if net.default_mtu is not None else ""
        table.add_row(net.name, str(net.cidr), context, dc, zone, env, mtu, desc)

    console.print(table)


@cli.command()
@click.argument("name")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "csv", "json"]),
    default="table",
    help="Output format (table, csv, json)",
)
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
def show(name, format, path):
    """Show details of a specific network"""
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

    width = 120 if not sys.stdout.isatty() else None
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
    console.print(f"[bold cyan]Reserve Gateway:[/bold cyan] {network.reserve_gateway}")
    console.print(f"[bold cyan]Reserve Internal:[/bold cyan] {network.reserve_internal}")

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
        sorted_reservations = sorted(network.effective_reservations, key=lambda r: r.networks[0].network_address)
        for res in sorted_reservations:
            usage = network.get_reservation_usage(res.id)
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
                return a.ip
            try:
                return ipaddress.ip_network(a.cidr.split("-")[0].strip(), strict=False).network_address
            except ValueError:
                return ipaddress.ip_address("0.0.0.0")

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

    # Normalize entity type (e.g. network -> networks, bridge-domain -> bridge_domains)
    normalized_type = entity_type.lower().replace("-", "_")
    if not normalized_type.endswith("s"):
        normalized_type += "s"

    if normalized_type not in ["networks", "epgs", "bridge_domains", "datacenters", "zones", "environments"]:
        click.echo(f"Error: Unknown entity type '{entity_type}'.")
        exit(1)

    from .loader import is_relational_mode

    relational = is_relational_mode(path)
    file_path = None

    if relational:
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
    else:
        # Legacy Mode - only networks exist as individual files
        if normalized_type != "networks":
            click.echo(
                f"Error: Entity type '{entity_type}' is only available in Relational Multi-Folder Database Mode."
            )
            exit(1)

        # Search recursively for network file
        for root, _, files in os.walk(path):
            for file in files:
                basename, ext = os.path.splitext(file.lower())
                if basename == name.lower() and ext in [".yaml", ".yml"]:
                    file_path = os.path.join(root, file)
                    break
            if file_path:
                break

        if not file_path:
            file_path = os.path.join(path, f"{name}.yaml")

    # Scaffold the directory if missing
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Resolve active editor from environment with safe terminal fallback
    editor = os.environ.get("EDITOR", "vi")

    click.echo(f"Opening '{file_path}' in editor '{editor}'...")
    try:
        subprocess.run([editor, file_path], check=True)
    except Exception as e:
        click.echo(f"Error: Failed to launch editor '{editor}': {e}")
        exit(1)


def run_format(path):
    """Format and order all keys, reservations, and allocations in database files."""
    import builtins
    import io

    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap, CommentedSeq

    yaml_rt = YAML(typ="rt")
    yaml_rt.preserve_quotes = True
    yaml_rt.indent(mapping=2, sequence=4, offset=2)
    yaml_rt.width = 120

    # Helper to sort sequence of mapping items by IP (supporting both direct 'ip' or 'cidr' keys)
    def get_item_start_ip(item):
        val = item.get("cidr") or item.get("ip")
        if not val:
            comment_val = item.get("comment", "")
            return (ipaddress.ip_address("255.255.255.255"), comment_val)
        val_str = str(val).split("-")[0].strip()
        try:
            return (ipaddress.ip_address(val_str), "")
        except ValueError:
            try:
                return (ipaddress.ip_network(val_str, strict=False).network_address, "")
            except ValueError:
                return (ipaddress.ip_address("255.255.255.255"), val_str)

    # Recursive function to format mapping structures
    def format_node(node):
        if isinstance(node, CommentedMap):
            cmap_keys = builtins.list(node.keys())
            sorted_keys = []

            # 1. Primary order fields
            primary_order = [
                "cidr",
                "description",
                "epg",
                "environment",
                "datacenter",
                "zone",
                "bridge_domain",
            ]
            for field in primary_order:
                if field in cmap_keys:
                    sorted_keys.append(field)

            # 2. Last keys
            last_keys = []
            for last_key in ["reservations", "allocations"]:
                if last_key in cmap_keys:
                    last_keys.append(last_key)

            # 3. Alphabetical other keys
            other = []
            for k in cmap_keys:
                if k not in sorted_keys and k not in last_keys:
                    other.append(k)
            other.sort()

            all_sorted_keys = sorted_keys + other + last_keys

            # Format nested structures inside
            for k in all_sorted_keys:
                node[k] = format_node(node[k])

            # Rebuild CommentedMap with sorted keys and preserved comments
            new_map = CommentedMap()
            if hasattr(node, "ca") and node.ca:
                new_map.ca.comment = node.ca.comment
            for k in all_sorted_keys:
                new_map[k] = node[k]
                if hasattr(node, "ca") and k in node.ca.items:
                    new_map.ca.items[k] = node.ca.items[k]
            return new_map

        elif isinstance(node, CommentedSeq) or isinstance(node, builtins.list):
            # If this is reservations list or allocations list, we sort the elements symmetrically!
            if len(node) > 0 and isinstance(node[0], CommentedMap):
                is_reservations = "cidr" in node[0] and "id" in node[0]
                is_allocations = "ip" in node[0] or "cidr" in node[0]
                if is_reservations or is_allocations:
                    node = sorted(node, key=get_item_start_ip)

            # Recursively format sequence elements
            new_seq = CommentedSeq()
            if hasattr(node, "ca") and node.ca:
                new_seq.ca.comment = node.ca.comment
            for i, item in enumerate(node):
                formatted_item = format_node(item)
                new_seq.append(formatted_item)
                if hasattr(node, "ca") and i in node.ca.items:
                    new_seq.ca.items[i] = node.ca.items[i]
            return new_seq

        return node

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
            formatted_data = format_node(data)

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


def main():
    cli()


if __name__ == "__main__":
    main()
