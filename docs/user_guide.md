# User Guide & API Reference

This document describes how to use the `net-mgmt` Click Command Line Interface (CLI), the programmatic Python API, and Jinja2 custom filters.

---

## 1. Click CLI Reference

The CLI main entrypoint is `net-mgmt`. You can configure the directory containing your networks by setting the `NET_MGMT_PATH` environment variable.

### General Options
- `--path`: Override the path to the networks directory (defaults to `networks`).

### Shell Completion
Since `net-mgmt` is built using the standard Python Click library, it natively supports complete tab-completion for all commands, options, and directories out-of-the-box.

To enable auto-completion for your active shell, run or add the corresponding command to your shell configuration file:

#### For Bash
Add this to your `~/.bashrc` or `~/.bash_profile`:
```bash
eval "$(_NET_MGMT_COMPLETE=bash_source net-mgmt)"
```

#### For Zsh
Add this to your `~/.zshrc`:
```zsh
eval "$(_NET_MGMT_COMPLETE=zsh_source net-mgmt)"
```

#### For Fish
Add this to your `~/.config/fish/config.fish`:
```fish
eval (env _NET_MGMT_COMPLETE=fish_source net-mgmt)
```

Restart your terminal or run `source ~/.bashrc` to instantly activate auto-completion!

---

### Command: `list`
Lists all networks in the database, displaying their core attributes (Name, CIDR, Context, Datacenter, Zone, Environment, MTU, and Description) in a clean terminal table. Features coordinate filters, column wrap configuration, and multiple output format filters.
* `--no-wrap`: Disables column text wrapping and truncation, forcing each network row to output as a single, fully expanded line (perfect for piping/scripting or displaying long names).
* `--format`, `-f`: Output format filter (`table`, `csv`, or `json`). Defaults to `table`.

```bash
# List all networks in tabular format
net-mgmt list

# List networks formatted as standard structured JSON
net-mgmt list --format json

# List networks formatted as CSV
net-mgmt list -f csv
```

---

### Command: `show`
Displays full structured details for a specific network (all metadata, active reservations, IP allocations, utilization statistics, and usable unreserved ranges). Supports structured format exports.
* `--format`, `-f`: Output format filter (`table`, `csv`, or `json`). Defaults to `table`.

```bash
# Show detailed tables of a network
net-mgmt show backend_net

# Show network properties as detailed, structured JSON (includes all sub-arrays)
net-mgmt show backend_net --format json

# Show network allocations and pools as standard CSV rows
net-mgmt show backend_net -f csv
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

### Command: `apply-template`
Applies a relative reservation template (YAML file containing offsets and required prefix lengths) to matching networks. It performs dynamic relative base-IP math to carve up networks, supports safe idempotency, and runs partial transactional rollbacks on individual pool validation conflicts.
* If `--network` is specified, it applies to that specific network.
* If `--network` is omitted, it automatically scans the entire database, matches all networks whose prefix length matches the template's required prefix, and applies the template to all of them!

```bash
# Apply a relative template to a specific network
net-mgmt apply-template --template templates/web-tier-22.yaml --network backend_net

# Apply a template globally to all matching /22 networks in the database
net-mgmt apply-template --template templates/web-tier-22.yaml
```

#### Relative Reservation Template Structure
A reservation template is a standard YAML file defining relative IP offset subnets. Because it uses relative offsets, the same template file can be cleanly applied to multiple networks across different base IP subnets:

```yaml
required_prefix_length: 25   # Apply only to networks matching prefix len /25 (alias: required_prefix_len)
reservations:
  - id: hosts
    cidr_offset: "0.0.0.0/27"   # CIDR offset relative to network base address
    comment: "Usable IP pool for client hosts"
    allocatable: true
  - id: tests
    cidr_offset: "0.0.0.64/27"  # Offset 64, size /27 (covers .64 to .95 of network)
    comment: "Reserved IP pool for test benches"
    allocatable: false
```

---

### Command: `edit`
Launches the interactive text editor defined in your shell env variable `$EDITOR` (falling back to `vi` or `nano`) to instantly open and edit any database entity YAML file (networks, epgs, datacenters, zones, bridge domains, environments).
- Automatically handles singular or plural entity type normalization (`network` ➔ `networks`).
- Automatically handles hyphen or underscore normalization (`bridge-domain` ➔ `bridge_domains`).
- In legacy flat databases, recursively walks subdirectories to find network files.
- Automatically scaffolds parent subdirectory directories if you are creating or editing a new file.

```bash
# Edit an EPG file inside your relational database
net-mgmt edit epg EPG_App

# Edit a network file inside your legacy or relational database
net-mgmt edit network example_net

# Edit a bridge domain file inside your relational database
net-mgmt edit bridge-domain BD_Prod
```

---

### Command: `format`
Standardizes, orders, and formats all keys, reservations, and allocations across every YAML database file in your repository.
- **Safety Validation Constraint**: To prevent formatting errors on an unstable or misconfigured repository, the format command **will only run if the entire database is 100% valid and passes all relational integrity/overlap checks.**
- **Key Ordering**: All keys are sorted symmetrically. Network files always start with `cidr`, followed by `description`, `epg`, `environment` (if present), other standard metadata fields in strict alphabetical order, and lastly `reservations` and `allocations`. Other relational files automatically adapt (starting with `description`, then `environment`, then alphabetical keys).
- **Symmetrical IP Sorting**:
  - `reservations` are sorted mathematically based on their starting IP address (from the beginning of the subnet block to the end).
  - `allocations` are sorted mathematically by their starting IP address.
- **Comment Preservation**: Built using `ruamel.yaml` in round-trip mode, fully preserving all line-level and inline/end-of-line comments.
- **Strict Idempotency**: Automatically skips writing to disk if the file is already formatted, preventing unnecessary git edits or file modification times (`mtime`) cache invalidations.

```bash
# Format and order all YAML files inside your networks database
net-mgmt format
```

---

### Command: `generate-markdown`
Renders the complete networks database into an output directory using decoupled, pluggable Jinja2 templates:
- Generates a central `README.md` index file containing a sleek, hierarchical nested bullet list representing your network topology.
- Generates dedicated relational subfolders (`datacenters/`, `zones/`, `environments/`, `bridge_domains/`, `epgs/`, and `networks/`) containing highly navigated cross-linked detail pages for every logical and physical entity.
- Fully supports custom HTML/Markdown Jinja2 template overrides.

```bash
# Render relational documentation inside /generated-docs directory using default templates
net-mgmt generate-markdown --output generated-docs

# Render documentation with a custom template overrides directory
net-mgmt generate-markdown --output generated-docs --templates my_templates/
```

#### Custom Template Overrides
The report engine looks for specific file names inside your templates directory and automatically falls back to standard defaults for any omitted ones:
- `index.md`: Renders the index `README.md` page (receives `tree` dict of nested subnets and `unassigned_networks` list).
- `datacenter.md`: Renders `datacenters/<dc_name>.md` pages (receives `name`, `properties`, and list of associated `networks`).
- `zone.md`: Renders `zones/<zone_name>.md` pages (receives `name`, `properties`, and list of associated `networks`).
- `environment.md`: Renders `environments/<env_name>.md` pages (receives `name`, `properties`, and list of associated `networks`).
- `bridge_domain.md`: Renders `bridge_domains/<bd_name>.md` pages (receives `name`, `properties`, and list of associated `networks`).
- `epg.md`: Renders `epgs/<epg_name>.md` pages (receives `name`, `properties`, and list of associated `networks`).
- `network.md`: Renders `networks/<net_name>.md` pages (receives `network` object).

---

### Command: `validate`
Runs a comprehensive relational integrity, CIDR overlap, and metadata constraint check over the entire networks database repository.
* `--format`: Automatically formats, standardizes, and orders all keys, reservations, and allocations across all database files **if and only if** the entire database successfully validates!

```bash
# Validate your networks database
net-mgmt validate

# Validate and automatically format/order all files upon successful validation
net-mgmt validate --format
```

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

### Native Dictionary Serialization (`to_dict`)
Every core model (`Allocation`, `Reservation`, `StaticRoute`, and `Network`) features a native, boilerplate-free `@property def to_dict(self) -> dict`. This property is universally accessible in both Python automation scripts and custom Jinja2 templates:

```python
# Convert a Network and all of its recursively nested lists to a Python dictionary
net_dict = net.to_dict

print(net_dict["name"])             # "backend_net"
print(net_dict["cidr"])             # "10.0.1.0/24"
print(net_dict["static_routes"])    # [{"cidr": "172.16.0.0/16", "gateway": "10.0.1.1"}]
```

#### Zero-Boilerplate Jinja2 Usage:
```jinja
{# Translate static route objects into a JSON array in your template #}
{{ network.static_routes | map(attribute='to_dict') | list | tojson }}

{# Convert an entire network to a JSON dict representation #}
{{ network.to_dict | tojson }}
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

#### Filter: `query_allocations`
Queries allocations inside a network by matching hostnames, IPs, or comments:
```jinja
{# Get all allocations inside a network containing the text 'db' #}
{% set db_servers = network | query_allocations('db') %}
{% for server in db_servers %}
IP: {{ server.ip }} | Host: {{ server.hostname }}
{% endfor %}
```

#### Filter: `find_or_allocate_hostname`
Finds or automatically allocates a single IP address by hostname:
```jinja
{# Find or allocate an IP for database node in backend_net #}
{% set network = 'backend_net' | network_by_name %}
{% set db_alloc = network | find_or_allocate_hostname('prod-db-01.internal') %}
Database IP: {{ db_alloc.ip }}
```

#### Filter: `find_or_allocate_range`
Finds or automatically allocates a contiguous range of IPs:
```jinja
{# Find or allocate a contiguous block of 3 IPs for a MetalLB service pool #}
{% set network = 'backend_net' | network_by_name %}
{% set lb_ips = network | find_or_allocate_range('MetalLB LoadBalancer Pool', 3) %}
LoadBalancer IPs:
{% for alloc in lb_ips %}
- {{ alloc.ip }}
{% endfor %}
```

#### Filter: `networks_in_epg`
Retrieves all subnets/networks associated with a specific EPG name:
```jinja
{# Get all networks belonging to EPG_App #}
{% set app_subnets = 'EPG_App' | networks_in_epg %}
{% for net in app_subnets %}
- {{ net.name }} ({{ net.cidr }})
{% endfor %}
```

#### Filter: `networks_in_bridge_domain`
Retrieves all subnets/networks associated with a specific Bridge Domain name:
```jinja
{# Get all networks belonging to BD_Prod #}
{% set prod_subnets = 'BD_Prod' | networks_in_bridge_domain %}
{% for net in prod_subnets %}
- {{ net.name }} ({{ net.cidr }})
{% endfor %}
```

#### Filter: `network_containing_ip`
Finds the parent `Network` object containing a given IP address (either a string IP, or an IP/CIDR object):
```jinja
{# 1. Find the parent network containing a standalone allocation IP #}
{% set parent_net = alloc.ip | network_containing_ip %}

{# 2. Read the prefix length #}
Parent Prefix: {{ parent_net.cidr.prefixlen }}
Parent Subnet: {{ parent_net.cidr }}
```

#### Relational Metadata Lookups: `*_by_name`
These filters allow you to retrieve the full, normalized dictionary properties for any physical or logical database entity directly from templates:
- `epg_by_name`: Looks up EPG metadata (e.g. `vlan`, `bridge_domain`, `environment`).
- `bridge_domain_by_name`: Looks up Bridge Domain metadata (e.g. `datacenter`, `zone`).
- `environment_by_name`: Looks up Environment variables.
- `zone_by_name`: Looks up Zone parameters.
- `datacenter_by_name`: Looks up Datacenter variables (e.g. `timeservers`, `dns_search`).

```jinja
{# Retrieve EPG metadata #}
{% set epg = 'EPG_App' | epg_by_name %}
EPG VLAN: {{ epg.vlan }}
EPG Bridge Domain: {{ epg.bridge_domain }}
EPG Environment Name: {{ epg.environment }}

{# Retrieve Bridge Domain metadata (resolving transitively) #}
{% set bd = epg.bridge_domain | bridge_domain_by_name %}
BD Datacenter: {{ bd.datacenter }}
BD Zone: {{ bd.zone }}

{# Retrieve Environment metadata (resolving transitively) #}
{% set env = epg.environment | environment_by_name %}
Env Timeservers: {{ env.timeservers | join(', ') }}
```

#### Filter: `query_networks`
Enables dynamic, first-class querying and filtering of networks by any of their attributes, including description substring searches:
```jinja
{# Get all networks whose description contains 'Storage' and belong to EPG_App #}
{% set storage_nets = get_networks() | query_networks(description='Storage', epg='EPG_App') %}
{% for net in storage_nets %}
- {{ net.name }} ({{ net.cidr }}) — *{{ net.description }}*
{% endfor %}
```

#### Filter: `apply_reservation_template`
Applies a relative reservation template (YAML file containing relative CIDR offsets) to a network dynamically inside a template:
```jinja
{# Apply our standard /24 web tier template to this network on the fly #}
{% set results = network | apply_reservation_template('templates/web-tier-24.yaml') %}
Applied: {{ results.applied | join(', ') }}
```
