# Bridge Domain: {{ name }}

## Properties
{% if properties.datacenter %}- **Datacenter**: [{{ properties.datacenter }}](../datacenters/{{ properties.datacenter }}.md){% endif %}
{% if properties.zone %}- **Zone**: [{{ properties.zone }}](../zones/{{ properties.zone }}.md){% endif %}
{% if properties.default_mtu %}- **Default MTU**: `{{ properties.default_mtu }}`{% endif %}

## Associated Subnets
| Network Name | CIDR | Context | Description |
| --- | --- | --- | --- |
{% for net in networks -%}
| [{{ net.name }}](../networks/{{ net.name }}.md) | `{{ net.cidr }}` | `{{ net.context }}` | {{ net.description or '' }} |
{% endfor -%}
