# Network Overview

{% if rows %}
| Topology / Network | CIDR | EPG | VLAN | Context | Description |
| :--- | :--- | :--- | :---: | :---: | :--- |
{% for row in rows -%}
| {{ row.label }} | {{ row.cidr }} | {{ row.epg }} | {{ row.vlan }} | {{ row.context }} | {{ row.description }} |
{% endfor %}
{% endif %}

{% if unassigned_networks %}
---

## 📂 Unassigned Networks
| Name | CIDR | Context | VLAN | Description |
| --- | --- | --- | --- | --- |
{% for net in unassigned_networks -%}
| [{{ net.name }}](networks/{{ net.name }}.md) | `{{ net.cidr }}` | `{{ net.context or 'default' }}` | `{{ net.vlan or 'None' }}` | {{ net.description or '' }} |
{% endfor %}
{% endif %}
