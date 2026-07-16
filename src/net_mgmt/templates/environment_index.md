# Environments Index

| Environment | Timeservers | DNS Nameservers |
| --- | --- | --- |
{% for name, props in environments.items() -%}
| [{{ name }}]({{ name }}.md) | {{ (props.timeservers or []) | join(', ') or 'None' }} | {{ (props.dns_nameservers or []) | join(', ') or 'None' }} |
{% endfor -%}
