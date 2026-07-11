# Technical Design Overview

This document describes the core architecture, data storage patterns, validation rules, and network modeling options of the Network Management System (`net-mgmt`).

---

## 1. System Architecture

The project is structured as a Python library with CLI and Jinja2 extension endpoints. The domain models are central to the architecture, containing all state, validation logic, and IP allocation operations. This ensures uniform behavior whether executing from a terminal, an automated pipeline, or a template rendering engine.

```text
       ┌────────────────────────┐
       │   CLI (net-mgmt)       │
       └───────────┬────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐     ┌───────────────────────┐
│           Core Library               │◄────┤    Jinja2 Filters     │
│   (src/net_mgmt/core.py & db.py)     │     └───────────────────────┘
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│           Loader Layer               │
│        (src/net_mgmt/loader.py)      │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│   Declarative YAML Files (networks/) │
└──────────────────────────────────────┘
```

---

## 2. Declarative YAML Storage

All network topologies, IP allocations, and IP reservations are stored declaratively as individual YAML files inside the `networks/` directory (configurable via `NET_MGMT_PATH` env var).

### Local Metadata Layout
A network is represented by a single YAML file matching its name (e.g. `networks/backend_net.yaml` corresponds to the network named `backend_net`):

```yaml
cidr: 10.0.2.0/24
vlan: 30
bridge_domain: BD_Prod
environment: production
epg: EPG_App
datacenter: DC_Frankfurt
zone: Trusted
routable: true
description: Application Backend
reservations:
  - id: db-vip
    cidr: 10.0.2.50/32
    comment: Database VIP
    allocatable: false
allocations:
  - ip: 10.0.2.20
    hostname: app-01
```

---

## 3. Options to Model Networks

The system supports two distinct methods to model and organize networks, giving teams maximum flexibility:

### Option A: Flat Metadata Files (Standalone)
Each network yaml file is self-contained. It explicitly defines its own topology metadata (like `datacenter`, `zone`, `bridge_domain`, `environment`, and `epg`) as local keys inside its file. This is highly portable and keeps each network's configuration independent.

### Option B: Centralized Hierarchy Configuration (Inheritance)
To keep individual network files clean and DRY (Don't Repeat Yourself), you can define a central hierarchy tree in a single configuration file named `networks/hierarchy.yaml`. 

This file maps the visual topology and can assign common settings (like `timeservers`, `dns_nameservers`, or `default_mtu`) at any tier. Individual network files then automatically inherit all parent attributes!

#### Example `networks/hierarchy.yaml`
```yaml
datacenters:
  DC_Frankfurt:
    timeservers:
      - 10.10.10.1
      - 10.10.10.2
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
                      - backend_net  # <-- backend_net automatically belongs here!
```

### Option C: Relational Multi-Folder Database
For larger, decoupled network repositories, you can model your network infrastructure as a normalized relational database spread across dedicated folders:

```text
net-mgmt-db/
├── datacenters/
│   └── DC_Frankfurt.yaml      # Defines timeservers, dns_nameservers
├── zones/
│   └── Trusted.yaml           # Defines dns_search
├── environments/
│   └── production.yaml        # Defines timeservers, environment-wide configs
├── bridge_domains/
│   └── BD_Prod.yaml           # Defines datacenter, zone, default_mtu
├── epgs/
│   └── EPG_App.yaml           # Defines bridge_domain, environment, vlan, default_mtu
└── networks/
    ├── backend_net.yaml       # Defines cidr, epg (inherits vlan, BD, DC, Zone, etc.)
    └── global-ovn-cluster.yaml# Defines cidr (independent subnet, no EPG)
```

#### Relational Reference Paths:
```text
BridgeDomain ➔ Refs: Datacenter (FK), Zone (FK) [Defines: default_mtu]
EPG          ➔ Refs: BridgeDomain (FK), Environment (FK) [Defines: vlan, default_mtu]
Network      ➔ Refs: EPG (FK, optional) [Defines: vlan, CIDR, reservations...]
```

---

## 4. Hierarchy & Inheritance Rules

When loading networks, the Loader resolves attributes using the following dynamic precedence:

### 4.1. Flat / Legacy Precedence
1. **Explicit Overrides**: If a property (such as `timeservers` or `dns_nameservers`) is explicitly defined inside the individual network's YAML file, it is always preferred.
2. **Centralized Membership**: If a network is listed under a leaf EPG inside `hierarchy.yaml`, it automatically inherits `datacenter`, `zone`, `bridge_domain`, `environment`, and `epg` properties, along with any common variables defined at those parent nodes.
3. **Explicit Metadata Traversal**: If a network yaml explicitly declares its path (e.g., `datacenter: DC_Frankfurt`), the Loader walks that exact path in `hierarchy.yaml` to dynamically inject parent-level variables (like `timeservers`) that the network did not declare locally.

### 4.2. Relational Precedence (Attribute Resolution Cascade)
When loading in Relational Mode, attributes (like `timeservers`, `dns_nameservers`, `dns_search`, or `default_mtu`) are resolved in order of specificity (the first defined value wins):
1. **Network** local overrides.
2. **EPG** configuration (if linked).
3. **Environment** configuration (if linked).
4. **BridgeDomain** configuration (if linked).
5. **Zone** configuration (if linked).
6. **Datacenter** configuration (if linked).

---

## 5. Network Validation Rules

The database enforces a series of strict structural and logical constraints:

1. **Routable Overlaps**: Routable networks share a global routing context. No two routable networks are allowed to overlap in their CIDR blocks.
2. **Context Overlaps**: Non-routable networks are grouped by their `context` metadata (default is `default`). No two networks in the same context are allowed to overlap. Overlaps are permitted *only* across different isolated contexts.
3. **Allocation Overlaps**: Within a network, no allocation can overlap with another allocation.
4. **Reservation Alignment**: All allocations must reside completely within an **allocatable** reservation (such as user-defined IP pools). They cannot reside in system reservations (network address, broadcast, gateway) or non-allocatable pools.
5. **Strict Relational Integrity (Relational Mode)**:
   - **ForeignKey Integrity**: If any reference (like `epg: EPG_App`) points to a non-existent entity file, loading fails.
   - **VLAN/BridgeDomain/Environment Match**: If a network explicitly defines any of these attributes, they must not conflict with the linked EPG's properties.
   - **Bridge Domain without EPG constraint**: A network cannot define `bridge_domain` without linking to an EPG.
   - **Datacenter/Zone Match**: Network's defined or inherited DC/Zone must match its EPG's BridgeDomain DC/Zone.
