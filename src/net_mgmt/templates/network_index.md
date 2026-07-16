# Networks Index

| Network | CIDR | EPG | VLAN | Context | Description |
| --- | --- | --- | --- | --- | --- |
{% for net in networks -%}
| [{{ net.name }}]({{ net.name }}.md) | `{{ net.cidr }}` | {% if net.epg %}[{{ net.epg }}](../epgs/{{ net.epg }}.md){% else %}None{% endif %} | {{ net.vlan or 'None' }} | `{{ net.context }}` | {{ net.description or '' }} |
{% endfor -%}
