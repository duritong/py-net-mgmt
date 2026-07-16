# Zones Index

| Zone | DNS Search | Timeservers |
| --- | --- | --- |
{% for name, props in zones.items() -%}
| [{{ name }}]({{ name }}.md) | {{ (props.dns_search or []) | join(', ') or 'None' }} | {{ (props.timeservers or []) | join(', ') or 'None' }} |
{% endfor -%}
