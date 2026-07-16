# EPGs Index

| EPG | Bridge Domain | Environment | VLAN |
| --- | --- | --- | --- |
{% for name, props in epgs.items() -%}
| [{{ name }}]({{ name }}.md) | {% if props.bridge_domain %}[{{ props.bridge_domain }}](../bridge_domains/{{ props.bridge_domain }}.md){% else %}None{% endif %} | {% if props.environment %}[{{ props.environment }}](../environments/{{ props.environment }}.md){% else %}None{% endif %} | {{ props.vlan or 'None' }} |
{% endfor -%}
