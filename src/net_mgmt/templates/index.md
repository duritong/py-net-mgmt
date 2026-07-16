# Network Overview

## 🗺️ Directory Hierarchy Tree

{% for dc, zones in tree.items() %}
- 🏢 **[{{ dc }}](datacenters/{{ dc }}.md)**
  {% for zone, bds in zones.items() %}
  - 📍 **[{{ zone }}](zones/{{ zone }}.md)**
    {% for bd, envs in bds.items() %}
      - 🌉 **[{{ bd }}](bridge_domains/{{ bd }}.md)**
        {% for env, epgs in envs.items() %}
          - 🌍 **[{{ env }}](environments/{{ env }}.md)**
            {% for epg, nets in epgs.items() %}
              - 🏷️ **[{{ epg }}](epgs/{{ epg }}.md)**
                {% for net in nets %}
                - 🔌 **[{{ net.name }}](networks/{{ net.name }}.md)** (`{{ net.cidr }}`){% if net.description %} — *{{ net.description }}*{% endif %}
                {% endfor %}
            {% endfor %}
        {% endfor %}
    {% endfor %}
  {% endfor %}
{% endfor %}

{% if unassigned_networks %}
---

## 📂 Unassigned Networks
| Name | CIDR | Context | VLAN | Description |
| --- | --- | --- | --- | --- |
{% for net in unassigned_networks -%}
| [{{ net.name }}](networks/{{ net.name }}.md) | `{{ net.cidr }}` | `{{ net.context or 'default' }}` | `{{ net.vlan or 'None' }}` | {{ net.description or '' }} |
{% endfor %}
{% endif %}
