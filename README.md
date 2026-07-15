# Net-Mgmt

A Python library and Click CLI for organizing, validating, and querying declarative network definitions, reservations, and IP allocations using a Relational Multi-Folder Database.

## Documentation Index

For comprehensive details on architecture, developer setups, and library usage, please refer to:
- [Technical Design Overview](docs/design_overview.md) (Database patterns, relational directories, validation constraints, and inheritance rules)
- [User Guide & API Reference](docs/user_guide.md) (Complete CLI references, pluggable template-driven reports, Python API examples, and Jinja2 filters)
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

## Relational Multi-Folder Database

The repository organizes your network infrastructure into standard, normalized database subdirectories:

```text
networks/
├── datacenters/
│   └── DC_Frankfurt.yaml      # Defines timeservers, dns_nameservers
├── zones/
│   └── Trusted.yaml           # Defines dns_search
├── environments/
│   └── production.yaml        # Defines timeservers, environment-wide configs
├── bridge_domains/
│   └── BD_Prod.yaml           # Defines: datacenter: DC_Frankfurt, zone: Trusted
├── epgs/
│   └── EPG_App.yaml           # Defines: bridge_domain: BD_Prod, environment: production, vlan: 30
└── networks/
    ├── backend_net.yaml       # Defines: cidr, epg: EPG_App (inherits vlan: 30, bd, etc.)
    └── global-ovn-cluster.yaml# Defines: cidr (independent subnet, no EPG)
```

### Attribute Resolution Cascade
To keep configurations clean and DRY, common variables (like `timeservers`, `dns_nameservers`, `dns_search`, or `default_mtu`) are resolved dynamically in order of specificity:
1. **Network** local overrides.
2. **EPG** configuration (if linked).
3. **Environment** configuration (if linked).
4. **BridgeDomain** configuration (if linked).
5. **Zone** configuration (if linked).
6. **Datacenter** configuration (if linked).

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
Checks for overlaps across globally routable networks, within the same context, and enforces strict relational integrity (ForeignKey and VLAN validations).
```bash
net-mgmt validate
```

### Generate Pluggable Markdown Documentation
Generates a highly navigated relational overview matching your database schema under `generated-docs/`, driven entirely by pluggable Jinja2 templates (Option B hierarchy index tree + cross-linked entity pages).
```bash
net-mgmt generate-markdown --output generated-docs
```

---

## Programmatic API Summary

The Python API is completely dual-mode: if your database folder contains relational directories, it loads in **Relational Mode**. Otherwise, it falls back to legacy flat folder configurations transparently.

```python
from net_mgmt import get_database, set_db_path
from net_mgmt.loader import save_network_to_file

set_db_path("networks")
networks = get_database()

# Find a network and modify it
net = next(n for n in networks if n.name == "backend_net")
net.description = "Updated description"

# Dry save (retains relational normalization on disk)
save_network_to_file(net)
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
