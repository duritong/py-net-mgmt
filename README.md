# Net-Mgmt

A Python library and Click CLI for organizing, validating, and querying declarative network definitions, reservations, and IP allocations.

## Documentation Index

For comprehensive details on architecture, developer setups, and library usage, please refer to:
- [Technical Design Overview](docs/design_overview.md) (Database patterns, network modeling options, validation constraints, and inheritance rules)
- [User Guide & API Reference](docs/user_guide.md) (Complete CLI references, Python API examples, and Jinja2 filter integrations)
- [Developer Guide](docs/developer_guide.md) (Workflows for contributing, adding fields, and executing the test suite)

---

## Installation

```bash
pip install .
```

## Running from Source (No Installation)

Ensure you have the dependencies installed (`pip install click PyYAML Jinja2 ruamel.yaml filelock rich`) and run it as a module from the `src` directory:

```bash
# Add the src directory to your PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# Run the CLI
python3 -m net_mgmt.cli list
```

---

## First-Class Network Hierarchy & Inheritance

The system organizes your subnets into a structured 6-tier topological hierarchy:
`Datacenter ➔ Zone ➔ Bridge Domain ➔ Environment ➔ EPG ➔ Network`

### Dynamic Inheritance (`networks/hierarchy.yaml`)
To avoid duplicating metadata across multiple network files, you can define a centralized topological tree in `networks/hierarchy.yaml`. Individual networks automatically inherit parent properties (such as `datacenter`, `zone`, `timeservers`, `dns_nameservers`, `default_mtu`, etc.):

```yaml
datacenters:
  DC_Frankfurt:
    timeservers:
      - 10.10.10.1
    zones:
      Trusted:
        dns_search:
          - trusted.internal
        bridge_domains:
          BD_Prod:
            environments:
              production:
                epgs:
                  EPG_App:
                    default_mtu: 1500
                    networks:
                      - backend_net  # <-- backend_net inherits all above settings!
```

---

## CLI Usage Summary

### List Networks
```bash
net-mgmt list
```

### Show Network Details
Displays beautiful `rich`-styled details for a network, including color-highlighted configurations, simple tabular listings of allocations/reservations, and contiguous human-readable unreserved intervals (e.g. `10.0.0.2 - 10.0.0.9`).
```bash
net-mgmt show backend_net
```

### Query VLANs by Hierarchy (`get-vlans`)
Lists unique, sorted VLAN IDs matching any combination of Datacenter, Zone, Bridge Domain, Environment, and EPG filters:
```bash
net-mgmt get-vlans --environment production --datacenter DC_Frankfurt --zone Trusted
```

### Validate Networks
Checks for overlaps across globally routable networks or within the same context.
```bash
net-mgmt validate
```

### Generate Markdown Documentation
Generates a highly structured, folder-style overview (`README.md`) matching your network hierarchy, alongside standalone detailed markdown documentation for every network.
```bash
net-mgmt generate-markdown --output docs
```

---

## Programmatic API Summary

```python
from net_mgmt import get_database, set_db_path
from net_mgmt.core import query_vlans

set_db_path("networks")
networks = get_database()

# Hierarchical querying of VLANs
vlan_ids = query_vlans(
    networks,
    environment="production",
    datacenter="DC_Frankfurt"
)
```

---

## Jinja2 Integration Filters

Includes custom template filters for rendering network automation templates:
- `network_by_name`: Retrieve a network object.
- `query_vlans`: Filter unique, sorted VLANs matching nested parameters.
- `vlans_in_environment`: Retrieve all VLANs in a specific environment.

```jinja
{# Template Examples #}
{{ 'backend_net' | network_by_name }}
{{ { 'environment': 'production', 'zone': 'Trusted' } | query_vlans }}
{{ 'production' | vlans_in_environment }}
```
