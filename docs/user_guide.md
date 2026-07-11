# User Guide & API Reference

This document describes how to use the `net-mgmt` Click Command Line Interface (CLI), the programmatic Python API, and Jinja2 custom filters.

---

## 1. Click CLI Reference

The CLI main entrypoint is `net-mgmt`. You can configure the directory containing your networks by setting the `NET_MGMT_PATH` environment variable.

### General Options
- `--path`: Override the path to the networks directory (defaults to `networks`).

---

### Command: `list`
Lists all networks in the database, displaying their core attributes (Name, CIDR, Context, Datacenter, Zone, Environment, MTU, and Description) in a clean terminal table.
```bash
net-mgmt list
```

---

### Command: `show`
Displays full structured details for a specific network (all metadata, active reservations, IP allocations, utilization statistics, and usable unreserved ranges).
```bash
net-mgmt show backend_net
```

---

### Command: `get-vlans`
Queries and lists unique, sorted VLAN IDs matching any combination of hierarchical filters (Datacenter, Zone, Bridge Domain, Environment, and EPG).
```bash
# Query all production VLANs in DC_Frankfurt
net-mgmt get-vlans --environment production --datacenter DC_Frankfurt

# Query dev VLANs in zone Trusted
net-mgmt get-vlans --environment dev --zone Trusted
```

---

### Command: `generate-markdown`
Renders the complete networks database into an output directory:
- Generates a central `README.md` containing a structured, segmented folder-style overview (H2-H5 headings) representing your topological hierarchy with flat tables.
- Generates individual, standalone detailed markdown files for each network (e.g. `backend_net.md`), complete with settings, active allocations, and free intervals.
```bash
# Render documentation inside /docs directory
net-mgmt generate-markdown --output docs
```

---

### Command: `migrate`
Migrates an existing flat network database (which may optionally use a centralized `hierarchy.yaml` configuration) into a fully normalized, relational multi-folder structure.
```bash
# Migrate flat database to relational database
net-mgmt migrate --path networks --output /path/to/new-relational-db
```
*Note: The migration script runs an exhaustive end-to-end safety parity verification checking all resolved attributes, IP allocations, and reservations to guarantee 100% data integrity before completing.*

---

## 2. Programmatic Python API

You can import `net-mgmt` directly into your own Python automation scripts.

### Loading & Saving the Database
The API is completely dual-mode: if your path contains the subdirectories `datacenters`, `zones`, `environments`, `bridge_domains`, `epgs`, and `networks`, it will automatically load and save in **Relational Mode**. Otherwise, it transparently falls back to **Legacy Mode** with `hierarchy.yaml`.

```python
from net_mgmt import get_database, set_db_path
from net_mgmt.loader import save_network_to_file

# Set the source directory (either a legacy directory or a relational multi-folder db)
set_db_path("networks")

# Load all networks (automatically applies inheritance from relational parent configurations or hierarchy.yaml)
networks = get_database()

# Find a network and modify it
net = next(n for n in networks if n.name == "backend_net")
net.description = "Updated description"

# Save changes back to its local YAML file safely.
# In Relational Mode, this automatically keeps configuration DRY by not serializing inherited metadata.
save_network_to_file(net)
```

### Hierarchical Querying of VLANs
```python
from net_mgmt.core import query_vlans

# Fetch production VLANs in Frankfurt
vlan_ids = query_vlans(
    networks,
    environment="production",
    datacenter="DC_Frankfurt"
)
print(f"Matched VLANs: {vlan_ids}")
```

---

## 3. Jinja2 Filters Integration

The project provides custom filters for rendering network automation templates (such as Ansible playbooks, OVN configurations, or BGP peer configs).

### Registering Filters
```python
import jinja2
from net_mgmt.jinja import register_filters

env = jinja2.Environment()
register_filters(env)
```

### Template Usage Examples

#### Filter: `network_by_name`
Finds a specific network object:
```jinja
{{ 'backend_net' | network_by_name }}
```

#### Filter: `query_vlans`
Retrieves sorted, unique VLANs matching a dictionary of filters:
```jinja
{% set query = { 'environment': 'production', 'datacenter': 'DC_Frankfurt' } %}
{% set vlans = query | query_vlans %}
Production VLANs: {{ vlans | join(', ') }}
```

#### Filter: `vlans_in_environment`
Retrieves all VLANs defined in a specific environment:
```jinja
{{ 'production' | vlans_in_environment }}
```
