# Bridge Domains Index

| Bridge Domain | Datacenter | Zone | Default MTU |
| --- | --- | --- | --- |
{% for name, props in bridge_domains.items() -%}
| [{{ name }}]({{ name }}.md) | {% if props.datacenter %}[{{ props.datacenter }}](../datacenters/{{ props.datacenter }}.md){% else %}None{% endif %} | {% if props.zone %}[{{ props.zone }}](../zones/{{ props.zone }}.md){% else %}None{% endif %} | {{ props.default_mtu or 'None' }} |
{% endfor -%}
