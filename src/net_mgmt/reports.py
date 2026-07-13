import os
from typing import List, Optional

import jinja2

from .core import Network
from .loader import load_yaml_files_from_subdir

DEFAULT_TEMPLATES = {
    "index.md": (
        "# Network Overview\n\n"
        "## 🗺️ Directory Hierarchy Tree\n\n"
        "{% for dc, zones in tree.items() %}\n"
        "- 🏢 **[{{ dc }}](datacenters/{{ dc }}.md)**\n"
        "  {% for zone, bds in zones.items() %}\n"
        "  - 📍 **[{{ zone }}](zones/{{ zone }}.md)**\n"
        "    {% for bd, envs in bds.items() %}\n"
        "      - 🌉 **[{{ bd }}](bridge_domains/{{ bd }}.md)**\n"
        "        {% for env, epgs in envs.items() %}\n"
        "          - 🌍 **[{{ env }}](environments/{{ env }}.md)**\n"
        "            {% for epg, nets in epgs.items() %}\n"
        "              - 🏷️ **[{{ epg }}](epgs/{{ epg }}.md)**\n"
        "                {% for net in nets %}\n"
        "                - 🔌 **[{{ net.name }}](networks/{{ net.name }}.md)** (`{{ net.cidr }}`)"
        "{% if net.description %} — *{{ net.description }}*{% endif %}\n"
        "                {% endfor %}\n"
        "            {% endfor %}\n"
        "        {% endfor %}\n"
        "    {% endfor %}\n"
        "  {% endfor %}\n"
        "{% endfor %}\n\n"
        "{% if unassigned_networks %}\n"
        "---\n\n"
        "## 📂 Unassigned Networks\n"
        "| Name | CIDR | Context | VLAN | Description |\n"
        "| --- | --- | --- | --- | --- |\n"
        "{% for net in unassigned_networks %}\n"
        "| [{{ net.name }}](networks/{{ net.name }}.md) | `{{ net.cidr }}` | "
        "`{{ net.context or 'default' }}` | `{{ net.vlan or 'None' }}` | {{ net.description or '' }} |\n"
        "{% endfor %}\n"
        "{% endif %}\n"
    ),
    "datacenter.md": (
        "# Datacenter: {{ name }}\n\n"
        "## Properties\n"
        "{% if properties.timeservers %}- **Timeservers**: `{{ properties.timeservers | join(', ') }}`{% endif %}\n"
        "{% if properties.dns_nameservers %}"
        "- **DNS Nameservers**: `{{ properties.dns_nameservers | join(', ') }}`{% endif %}\n"
        "{% if properties.dns_search %}- **DNS Search**: `{{ properties.dns_search | join(', ') }}`{% endif %}\n"
        "{% if properties.default_mtu %}- **Default MTU**: `{{ properties.default_mtu }}`{% endif %}\n\n"
        "## Associated Subnets\n"
        "| Network Name | CIDR | Context | Description |\n"
        "| --- | --- | --- | --- |\n"
        "{% for net in networks %}\n"
        "| [{{ net.name }}](../networks/{{ net.name }}.md) | `{{ net.cidr }}` | "
        "`{{ net.context }}` | {{ net.description or '' }} |\n"
        "{% endfor %}\n"
    ),
    "zone.md": (
        "# Zone: {{ name }}\n\n"
        "## Properties\n"
        "{% if properties.timeservers %}- **Timeservers**: `{{ properties.timeservers | join(', ') }}`{% endif %}\n"
        "{% if properties.dns_nameservers %}"
        "- **DNS Nameservers**: `{{ properties.dns_nameservers | join(', ') }}`{% endif %}\n"
        "{% if properties.dns_search %}- **DNS Search**: `{{ properties.dns_search | join(', ') }}`{% endif %}\n"
        "{% if properties.default_mtu %}- **Default MTU**: `{{ properties.default_mtu }}`{% endif %}\n\n"
        "## Associated Subnets\n"
        "| Network Name | CIDR | Context | Description |\n"
        "| --- | --- | --- | --- |\n"
        "{% for net in networks %}\n"
        "| [{{ net.name }}](../networks/{{ net.name }}.md) | `{{ net.cidr }}` | "
        "`{{ net.context }}` | {{ net.description or '' }} |\n"
        "{% endfor %}\n"
    ),
    "environment.md": (
        "# Environment: {{ name }}\n\n"
        "## Properties\n"
        "{% if properties.timeservers %}- **Timeservers**: `{{ properties.timeservers | join(', ') }}`{% endif %}\n"
        "{% if properties.dns_nameservers %}"
        "- **DNS Nameservers**: `{{ properties.dns_nameservers | join(', ') }}`{% endif %}\n"
        "{% if properties.dns_search %}- **DNS Search**: `{{ properties.dns_search | join(', ') }}`{% endif %}\n"
        "{% if properties.default_mtu %}- **Default MTU**: `{{ properties.default_mtu }}`{% endif %}\n\n"
        "## Associated Subnets\n"
        "| Network Name | CIDR | Context | Description |\n"
        "| --- | --- | --- | --- |\n"
        "{% for net in networks %}\n"
        "| [{{ net.name }}](../networks/{{ net.name }}.md) | `{{ net.cidr }}` | "
        "`{{ net.context }}` | {{ net.description or '' }} |\n"
        "{% endfor %}\n"
    ),
    "bridge_domain.md": (
        "# Bridge Domain: {{ name }}\n\n"
        "## Properties\n"
        "{% if properties.datacenter %}- **Datacenter**: "
        "[{{ properties.datacenter }}](../datacenters/{{ properties.datacenter }}.md){% endif %}\n"
        "{% if properties.zone %}- **Zone**: [{{ properties.zone }}](../zones/{{ properties.zone }}.md){% endif %}\n"
        "{% if properties.default_mtu %}- **Default MTU**: `{{ properties.default_mtu }}`{% endif %}\n\n"
        "## Associated Subnets\n"
        "| Network Name | CIDR | Context | Description |\n"
        "| --- | --- | --- | --- |\n"
        "{% for net in networks %}\n"
        "| [{{ net.name }}](../networks/{{ net.name }}.md) | `{{ net.cidr }}` | "
        "`{{ net.context }}` | {{ net.description or '' }} |\n"
        "{% endfor %}\n"
    ),
    "epg.md": (
        "# EPG: {{ name }}\n\n"
        "## Properties\n"
        "- **VLAN**: `{{ properties.vlan or 'None' }}`\n"
        "- **Bridge Domain**: [{{ properties.bridge_domain }}](../bridge_domains/{{ properties.bridge_domain }}.md)\n"
        "- **Environment**: [{{ properties.environment }}](../environments/{{ properties.environment }}.md)\n"
        "{% if properties.default_mtu %}- **MTU**: `{{ properties.default_mtu }}`{% endif %}\n\n"
        "## Associated Subnets\n"
        "| Network Name | CIDR | Context | Description |\n"
        "| --- | --- | --- | --- |\n"
        "{% for net in networks %}\n"
        "| [{{ net.name }}](../networks/{{ net.name }}.md) | `{{ net.cidr }}` | "
        "`{{ net.context }}` | {{ net.description or '' }} |\n"
        "{% endfor %}\n"
    ),
    "network.md": (
        "# {{ network.name }}\n\n"
        "## Settings\n"
        "- **CIDR**: `{{ network.cidr }}`\n"
        "- **Context**: `{{ network.context }}`\n"
        "{% if network.description %}- **Description**: {{ network.description }}{% endif %}\n"
        "- **VLAN**: `{{ network.vlan or 'None' }}`\n"
        "- **Bridge Domain**: {% if network.bridge_domain %}"
        "[{{ network.bridge_domain }}](../bridge_domains/{{ network.bridge_domain }}.md){% else %}`None`{% endif %}\n"
        "- **Environment**: {% if network.environment %}"
        "[{{ network.environment }}](../environments/{{ network.environment }}.md){% else %}`None`{% endif %}\n"
        "- **EPG**: {% if network.epg %}[{{ network.epg }}](../epgs/{{ network.epg }}.md){% else %}`None`{% endif %}\n"
        "- **MTU**: `{{ network.default_mtu or 'None' }}`\n\n"
        "- **DNS Nameservers**: `{{ (network.dns_nameservers or []) | join(', ') or 'None' }}`\n"
        "- **DNS Search**: `{{ (network.dns_search or []) | join(', ') or 'None' }}`\n"
        "- **Timeservers**: `{{ (network.timeservers or []) | join(', ') or 'None' }}`\n\n"
        "{% if network.static_routes %}\n"
        "- **Static Routes**:\n"
        "  {% for route in network.static_routes %}\n"
        "  - `{{ route.cidr }} via {{ route.gateway }}`\n"
        "  {% endfor %}\n"
        "{% else %}\n"
        "- **Static Routes**: `None`\n"
        "{% endif %}\n\n"
        "- **Zone**: {% if network.zone %}"
        "[{{ network.zone }}](../zones/{{ network.zone }}.md){% else %}`None`{% endif %}\n"
        "- **Datacenter**: {% if network.datacenter %}"
        "[{{ network.datacenter }}](../datacenters/{{ network.datacenter }}.md){% else %}`None`{% endif %}\n"
        "- **Routable**: `{{ network.routable }}`\n"
        "- **Reserve Gateway**: `{{ network.reserve_gateway }}`\n"
        "- **Reserve Internal**: `{{ network.reserve_internal }}`\n\n"
        "## Reservations\n"
        "{% if network.effective_reservations %}\n"
        "| ID | CIDR | Comment | Allocatable | Allocations | Usage |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "{% for res in network.effective_reservations %}\n"
        "{% set usage = network.get_reservation_usage(res.id) %}\n"
        "| {{ res.id }} | {{ res.cidr }} | {{ res.comment }} | {{ res.allocatable }} | "
        "{{ usage.count }} | {{ usage.count }}/{{ usage.total }} "
        '({{ "%.1f" | format(usage.percent) }}%) |\n'
        "{% endfor %}\n"
        "{% else %}\n"
        "_No reservations._\n"
        "{% endif %}\n\n"
        "{% if network.allocations %}\n"
        "## Allocations\n"
        "| IP/CIDR | Hostname/Comment |\n"
        "| --- | --- |\n"
        "{% for alloc in network.allocations %}\n"
        "{% if alloc.ip %}\n"
        "| {{ alloc.ip }} | {{ alloc.hostname }} |\n"
        "{% else %}\n"
        "| {{ alloc.cidr }} | {{ alloc.comment }} |\n"
        "{% endif %}\n"
        "{% endfor %}\n"
        "{% endif %}\n\n"
        "{% set unreserved = network.get_unreserved_display_ranges() %}\n"
        "{% if unreserved %}\n"
        "## Unreserved Ranges\n"
        "{% for rng in unreserved %}\n"
        "- `{{ rng }}`\n"
        "{% endfor %}\n"
        "{% endif %}\n"
    ),
}


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

    # 2. Configure Jinja2 environment with ChoiceLoader for overrides
    if templates_dir and os.path.isdir(templates_dir):
        loader = jinja2.ChoiceLoader([jinja2.FileSystemLoader(templates_dir), jinja2.DictLoader(DEFAULT_TEMPLATES)])
    else:
        loader = jinja2.DictLoader(DEFAULT_TEMPLATES)

    env = jinja2.Environment(loader=loader)

    # 3. Create relational subdirectories under output_dir
    subdirs = ["datacenters", "zones", "environments", "bridge_domains", "epgs", "networks"]
    for subdir in subdirs:
        os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)

    # 4. Load raw metadata files to render complete list of entities
    datacenters = load_yaml_files_from_subdir(db_dir, "datacenters")
    zones = load_yaml_files_from_subdir(db_dir, "zones")
    environments = load_yaml_files_from_subdir(db_dir, "environments")
    bridge_domains = load_yaml_files_from_subdir(db_dir, "bridge_domains")
    epgs = load_yaml_files_from_subdir(db_dir, "epgs")

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
