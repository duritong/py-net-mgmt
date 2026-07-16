# Datacenters Index

| Datacenter | Timeservers | DNS Nameservers | Default MTU |
| --- | --- | --- | --- |
{% for name, props in datacenters.items() -%}
| [{{ name }}]({{ name }}.md) | {{ (props.timeservers or []) | join(', ') or 'None' }} | {{ (props.dns_nameservers or []) | join(', ') or 'None' }} | {{ props.default_mtu or 'None' }} |
{% endfor -%}
