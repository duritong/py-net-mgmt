# Zone: {{ name }}

## Properties
{% if properties.timeservers %}- **Timeservers**: `{{ properties.timeservers | join(', ') }}`{% endif %}
{% if properties.dns_nameservers %}- **DNS Nameservers**: `{{ properties.dns_nameservers | join(', ') }}`{% endif %}
{% if properties.dns_search %}- **DNS Search**: `{{ properties.dns_search | join(', ') }}`{% endif %}
{% if properties.default_mtu %}- **Default MTU**: `{{ properties.default_mtu }}`{% endif %}

## Associated Subnets
| Network Name | CIDR | Context | Description |
| --- | --- | --- | --- |
{% for net in networks -%}
| [{{ net.name }}](../networks/{{ net.name }}.md) | `{{ net.cidr }}` | `{{ net.context }}` | {{ net.description or '' }} |
{% endfor -%}
