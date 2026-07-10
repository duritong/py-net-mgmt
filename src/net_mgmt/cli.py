import ipaddress

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
def validate(path):
    """Validate all networks"""
    set_db_path(path)
    try:
        networks = get_database(force_reload=True)
        click.echo(f"Successfully validated {len(networks)} networks.")
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)


@cli.command()
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
def list(path):
    """List all available networks"""
    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    if not networks:
        click.echo("No networks found.")
        return

    import sys

    width = 120 if not sys.stdout.isatty() else None
    console = Console(width=width)
    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("CIDR", style="green")
    table.add_column("Context", style="magenta")
    table.add_column("Datacenter", style="yellow")
    table.add_column("Zone", style="blue")
    table.add_column("MTU", justify="right")
    table.add_column("Description")

    for net in networks:
        desc = net.description or ""
        dc = net.datacenter or ""
        zone = net.zone or ""
        context = net.context or "default"
        mtu = str(net.default_mtu) if net.default_mtu is not None else ""
        table.add_row(net.name, str(net.cidr), context, dc, zone, mtu, desc)

    console.print(table)


@cli.command()
@click.argument("name")
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
def show(name, path):
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


@cli.command()
@click.option("--path", envvar="NET_MGMT_PATH", default="networks", help="Path to networks directory")
@click.option("--output", "-o", default="docs", help="Output directory for markdown files")
def generate_markdown(path, output):
    """Generate markdown overview in an output directory"""
    from .reports import generate_markdown_report

    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    generate_markdown_report(networks, output)
    click.echo(f"Markdown reports generated in {output}")


def main():
    cli()


if __name__ == "__main__":
    main()
