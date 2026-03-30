# Net-Mgmt

A Python library and CLI for organizing network definitions.

## Installation

```bash
pip install .
```

## Running from Source (No Installation)

If you want to try out the CLI without installing it, ensure you have the dependencies installed (`pip install click PyYAML Jinja2`) and run it as a module from the `src` directory:

```bash
# Add the src directory to your PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# Run the CLI
python3 -m net_mgmt.cli list
```

## Configuration

You can set the default path to your network definitions using the `NET_MGMT_PATH` environment variable.

```bash
export NET_MGMT_PATH=/path/to/my/networks
```

If not set, it defaults to `networks` in the current directory. The CLI `--path` argument overrides this variable.

## Running from Outside the Project Directory

If you are running the `net-mgmt` command from a different location, you need to point it to your `networks` directory.

**Option 1: Using the `--path` argument**

```bash
# Assuming your networks are in /home/user/projects/net-mgmt/networks
net-mgmt list --path /home/user/projects/net-mgmt/networks
```

**Option 2: Using the Environment Variable**

```bash
export NET_MGMT_PATH=/home/user/projects/net-mgmt/networks
net-mgmt list
```

## CLI Usage

### List Networks

```bash
net-mgmt list
# Or specify path explicitly
net-mgmt list --path /custom/networks
```

### Show Network Details

```bash
net-mgmt show <network_name>
```

### Validate Networks

Checks for overlapping CIDRs among globally routable networks, as well as overlapping CIDRs within the same `context` (allowing overlapping non-routable networks if they belong to different contexts/VRFs).

```bash
net-mgmt validate
```

### Add Allocations

You can add allocations directly via the CLI. The command supports both single IPs and subnets/ranges.

**Single IP Allocation:**
```bash
net-mgmt add-allocation <network_name> --ip <ip> --hostname <hostname>
```

**Subnet/Range Allocation:**
```bash
net-mgmt add-allocation <network_name> --cidr <cidr_or_range> --comment <comment>
```

### Generate Markdown Overview

```bash
net-mgmt generate-markdown --output overview.md
# Or use the short alias
net-mgmt generate-markdown -o overview.md
```

## Library Usage

You can load and switch between different network databases at runtime.

```python
from net_mgmt import get_database, set_db_path

# Load from default path (or NET_MGMT_PATH env var)
networks = get_database()
print(f"Loaded {len(networks)} networks from default path")

# Get next free IP
net = networks[0]
try:
    ip = net.get_next_free_ip()
    print(f"Next free IP: {ip}")
except ValueError as e:
    print(f"Error: {e}")

# Query allocations
matches = net.query_allocations("web-server")
for alloc in matches:
    print(alloc)

# Switch to a different database directory
# This clears the cache and reloads/validates on the next get_database() call
set_db_path("/path/to/other/networks")
other_networks = get_database()
print(f"Loaded {len(other_networks)} networks from new path")
```

## Jinja2 Integration

The filters automatically load and validate the database if no network list is provided. This is cached globally.

```python
from jinja2 import Environment
from net_mgmt import register_filters

env = Environment()
register_filters(env)
# Templates can now use:
# {{ 'net_name' | network_by_name }}
# {{ 'BD1' | networks_in_bridge_domain }}
# {{ my_network | query_allocations('web-') }}
```

## Data Structure

Each network is defined in a YAML file in the `networks/` directory.

Example `networks/example_net.yaml`:

```yaml
cidr: 10.0.0.0/24
vlan: 10
bridge_domain: BD_Prod
epg: EPG_Web
datacenter: DC_Frankfurt
zone: Trusted
context: vrf_prod  # Default is 'default'. Networks in the same context cannot overlap.
routable: true  # Default is true. Set to false to skip global overlap validation.
description: Production Web Tier
reserve_gateway: true # Default true. Blocks allocation of .1
reserve_internal: true # Default true. Blocks allocation of .2-.5
reservations:
  - id: gw
    cidr: 10.0.0.1/32
    comment: Gateway
    allocatable: false # Default false. Cannot allocate from here.
  - id: pool-01
    cidr: 10.0.0.20-10.0.0.30
    comment: Reserved Pool
    allocatable: true # Can allocate IPs from this pool.
allocations:
  - ip: 10.0.0.20
    hostname: host-01
  - cidr: 10.0.0.25-10.0.0.26
    comment: Management Cluster
```
