# EPG: {{ name }}

## Properties
- **VLAN**: `{{ properties.vlan or 'None' }}`
- **Bridge Domain**: [{{ properties.bridge_domain }}](../bridge_domains/{{ properties.bridge_domain }}.md)
- **Environment**: [{{ properties.environment }}](../environments/{{ properties.environment }}.md)
{% if properties.default_mtu %}- **MTU**: `{{ properties.default_mtu }}`{% endif %}

## Associated Subnets
| Network Name | CIDR | Context | Description |
| --- | --- | --- | --- |
{% for net in networks -%}
| [{{ net.name }}](../networks/{{ net.name }}.md) | `{{ net.cidr }}` | `{{ net.context }}` | {{ net.description or '' }} |
{% endfor -%}
