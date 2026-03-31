import ipaddress

import click

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

    click.echo(
        f"{'Name':<20} {'CIDR':<20} {'Context':<15} {'Datacenter':<15} {'Zone':<15} {'MTU':<8} {'Description':<40}"
    )
    click.echo("-" * 134)
    for net in networks:
        desc = net.description or ""
        dc = net.datacenter or ""
        zone = net.zone or ""
        context = net.context or "default"
        mtu = str(net.default_mtu) if net.default_mtu is not None else ""
        click.echo(f"{net.name:<20} {str(net.cidr):<20} {context:<15} {dc:<15} {zone:<15} {mtu:<8} {desc:<40}")


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

    click.echo(f"Name: {network.name}")
    click.echo(f"CIDR: {network.cidr}")
    click.echo(f"Context: {network.context}")
    click.echo(f"Description: {network.description}")
    click.echo(f"VLAN: {network.vlan}")
    click.echo(f"Bridge Domain: {network.bridge_domain}")
    click.echo(f"EPG: {network.epg}")
    click.echo(f"Default MTU: {network.default_mtu}")
    click.echo(f"DNS Nameservers: {', '.join(network.dns_nameservers) if network.dns_nameservers else 'None'}")
    click.echo(f"DNS Search: {', '.join(network.dns_search) if network.dns_search else 'None'}")
    click.echo(f"Timeservers: {', '.join(network.timeservers) if network.timeservers else 'None'}")

    if network.static_routes:
        routes_str = ", ".join([f"{sr.cidr} via {sr.gateway}" for sr in network.static_routes])
    else:
        routes_str = "None"
    click.echo(f"Static Routes: {routes_str}")

    click.echo(f"Zone: {network.zone}")
    click.echo(f"Datacenter: {network.datacenter}")
    click.echo(f"Routable: {network.routable}")
    click.echo(f"Reserve Gateway: {network.reserve_gateway}")
    click.echo(f"Reserve Internal: {network.reserve_internal}")

    if network.effective_reservations:
        click.echo("\nReservations:")
        click.echo(f"{'ID':<15} {'CIDR':<20} {'Comment':<30} {'Allocatable':<12} {'Allocations':<12} {'Usage':<10}")
        click.echo("-" * 105)
        # Sort reservations by their starting IP address
        sorted_reservations = sorted(network.effective_reservations, key=lambda r: r.networks[0].network_address)
        for res in sorted_reservations:
            usage = network.get_reservation_usage(res.id)
            alloc_count = usage["count"]
            usage_pct = f"{usage['percent']:.1f}%"
            click.echo(
                f"{res.id:<15} {str(res.cidr):<20} {res.comment:<30} {str(res.allocatable):<12} "
                f"{alloc_count:<12} {usage_pct:<10}"
            )
    else:
        click.echo("\nNo reservations.")

    if network.allocations:
        click.echo("\nAllocations:")
        click.echo(f"{'IP/CIDR':<30} {'Hostname/Comment':<40}")
        click.echo("-" * 70)

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
                click.echo(f"{str(alloc.ip):<30} {alloc.hostname:<40}")
            else:
                click.echo(f"{alloc.cidr:<30} {alloc.comment:<40}")

    # Show unreserved ranges
    unreserved = network.get_unreserved_ranges()
    if unreserved:
        click.echo("\nUnreserved Ranges:")
        for net in unreserved:
            click.echo(f"  {str(net)}")


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
@click.option("--output", "-o", default="overview.md", help="Output markdown file")
def generate_markdown(path, output):
    """Generate markdown overview"""
    from .reports import generate_markdown_report

    set_db_path(path)
    try:
        networks = get_database()
    except ValueError as e:
        click.echo(f"Validation Error: {e}")
        exit(1)

    generate_markdown_report(networks, output)
    click.echo(f"Markdown report generated at {output}")


def main():
    cli()


if __name__ == "__main__":
    main()
