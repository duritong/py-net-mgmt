# {{ network.name }}

## Settings
- **CIDR**: `{{ network.cidr }}`
{% if network.aggregate %}- **Aggregate Network**: True{% endif %}
{% set parent = network.get_parent_aggregate(all_networks) if all_networks else None %}
{% if parent %}- **Parent Aggregate**: [{{ parent.name }}]({{ parent.name }}.md) (`{{ parent.cidr }}`){% endif %}
- **Context**: `{{ network.context }}`
{% if network.description %}- **Description**: {{ network.description }}{% endif %}
- **VLAN**: `{{ network.vlan or 'None' }}`
- **Bridge Domain**: {% if network.bridge_domain %}[{{ network.bridge_domain }}](../bridge_domains/{{ network.bridge_domain }}.md){% else %}`None`{% endif %}
- **Environment**: {% if network.environment %}[{{ network.environment }}](../environments/{{ network.environment }}.md){% else %}`None`{% endif %}
- **EPG**: {% if network.epg %}[{{ network.epg }}](../epgs/{{ network.epg }}.md){% else %}`None`{% endif %}
- **MTU**: `{{ network.default_mtu or 'None' }}`

- **DNS Nameservers**: `{{ (network.dns_nameservers or []) | join(', ') or 'None' }}`
- **DNS Search**: `{{ (network.dns_search or []) | join(', ') or 'None' }}`
- **Timeservers**: `{{ (network.timeservers or []) | join(', ') or 'None' }}`

{% if network.static_routes %}
- **Static Routes**:
  {% for route in network.static_routes %}
  - `{{ route.cidr }} via {{ route.gateway }}`
  {% endfor %}
{% else %}
- **Static Routes**: `None`
{% endif %}

- **Zone**: {% if network.zone %}[{{ network.zone }}](../zones/{{ network.zone }}.md){% else %}`None`{% endif %}
- **Datacenter**: {% if network.datacenter %}[{{ network.datacenter }}](../datacenters/{{ network.datacenter }}.md){% else %}`None`{% endif %}
- **Routable**: `{{ network.routable }}`
- **Reserve Gateway**: `{{ network.reserve_gateway }}`
- **Reserve Internal**: `{{ network.reserve_internal }}`
- **Reserve Internal Until**: `{{ network.reserve_internal_until }}`

## Reservations
{% if network.effective_reservations -%}
| ID | CIDR | Comment | Allocatable | Allocations | Usage |
| --- | --- | --- | --- | --- | --- |
{% for res in network.effective_reservations -%}
{% set usage = network.get_reservation_usage(res.id, res.cidr) -%}
| {{ res.id }} | {{ res.cidr }} | {{ res.comment }} | {{ res.allocatable }} | {{ usage.count }} | {{ usage.count }}/{{ usage.total }} ({{ "%.1f" | format(usage.percent) }}%) |
{% endfor -%}
{% else -%}
_No reservations._
{% endif -%}

{% if network.allocations -%}
## Allocations
| IP/CIDR | Hostname/Comment |
| --- | --- |
{% for alloc in network.allocations -%}
{% if alloc.ip -%}
| {{ alloc.ip }} | {{ alloc.hostname }} |
{% else -%}
| {{ alloc.cidr }} | {{ alloc.comment }} |
{% endif -%}
{% endfor -%}
{% endif -%}

{% set unreserved = network.get_unreserved_display_ranges() -%}
{% if unreserved -%}
## Unreserved Ranges
{% for rng in unreserved -%}
- `{{ rng }}`
{% endfor -%}
{% endif -%}

{% if network.aggregate %}
{% set subnets = network.get_subnets(all_networks) if all_networks else [] %}
{% if subnets %}
## Sub-Prefixes (Subnets)
| Subnet | CIDR | EPG | VLAN | Bridge Domain | Description |
| --- | --- | --- | --- | --- | --- |
{% for sub in subnets -%}
| [{{ sub.name }}]({{ sub.name }}.md) | `{{ sub.cidr }}` | {% if sub.epg %}[{{ sub.epg }}](../epgs/{{ sub.epg }}.md){% else %}`None`{% endif %} | {{ sub.vlan or 'None' }} | {% if sub.bridge_domain %}[{{ sub.bridge_domain }}](../bridge_domains/{{ sub.bridge_domain }}.md){% else %}`None`{% endif %} | {{ sub.description or '' }} |
{% endfor -%}
{% endif %}

{% set unallocated = network.get_unallocated_subnets(all_networks) if all_networks else [] %}
{% if unallocated %}
## Available Sub-Prefix Capacity
{% for block in unallocated -%}
- `{{ block }}`
{% endfor -%}
{% endif %}
{% endif %}
