# Relational Database Migration Plan (Proposed)

This document details the architecture design and implementation plan to transition the `net-mgmt` datastructure from a monolithic flat layout into a **Relational Multi-Folder Database**. It also details an automated, one-time CLI migration strategy for existing users.

---

## 1. Schema & Relationship Design

To prevent a centralized configuration file from becoming a bottleneck, we decompose the metadata hierarchy into normalized, composable files under dedicated subdirectories. 

The physical and logical entities are decoupled and related using **Foreign Keys**:

```text
Datacenter   (global config: e.g. timeservers, dns_nameservers)
Zone         (global config: e.g. dns_search)
Environment  (global config: e.g. timeservers)

BridgeDomain ➔ Refs: Datacenter (FK), Zone (FK) [Defines: default_mtu]
EPG          ➔ Refs: BridgeDomain (FK), Environment (FK) [Defines: vlan, default_mtu]
Network      ➔ Refs: EPG (FK, optional) [Defines: vlan, CIDR, reservations...]
```

---

## 2. Directory Structure on Disk

The directory structure in the networks repository (configured via `NET_MGMT_PATH`) will now consist of standard subfolders:

```text
net-mgmt-db/
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
    └── global-ovn-cluster.yaml# Defines: cidr (independent subnet, no epg)
```

---

## 3. Attribute Resolution Cascade

When querying metadata fields (like `timeservers`, `dns_nameservers`, `dns_search`, or `default_mtu`) for a given Network, the system resolves them in order of specificity (the first defined value wins):

1. **Network** local overrides.
2. **EPG** configuration (if linked).
3. **Environment** configuration (if linked).
4. **BridgeDomain** configuration (if linked).
5. **Zone** configuration (if linked).
6. **Datacenter** configuration (if linked).

---

## 4. Strict Relational Validations

To guarantee absolute database consistency, the Loader enforces "fail-fast" checks at load-time:

1. **ForeignKey Integrity**: If any reference (e.g. `epg: EPG_App` on a Network) points to a non-existent file, loading fails with a `ValueError`.
2. **VLAN Match check**: If a Network explicitly defines a `vlan` that conflicts with its EPG's `vlan`, validation fails.
3. **Bridge Domain Match check**: If a Network explicitly defines a `bridge_domain` that conflicts with its EPG's `bridge_domain`, validation fails.
4. **Environment Match check**: If a Network explicitly defines an `environment` that conflicts with its EPG's `environment`, validation fails.
5. **Datacenter/Zone Match check**: If a Network defines local `datacenter` or `zone` attributes that conflict with those defined on its EPG's resolved `BridgeDomain`, validation fails.

---

## 5. One-Time Automated CLI Migration

To make this transition effortless for existing users with flat files, we will introduce a new CLI migration command:

```bash
net-mgmt migrate --output /path/to/new-layout
```

### How the Automated Migration Script Works:
1. **Analyze existing flat files**: The tool scans all `.yaml` files in the current `networks/` folder.
2. **Extract unique entities**: It identifies all unique:
   - Datacenters (e.g., `DC_Frankfurt`)
   - Zones (e.g., `Trusted`)
   - Environments (e.g., `production` - inferred from file or defaults)
   - Bridge Domains (e.g., `BD_Prod` mapping to `datacenter` and `zone`)
   - EPGs (e.g., `EPG_App` mapping to `bridge_domain` and `vlan`)
3. **Auto-populate subfolders**: It automatically creates the target directories and populates the normalized configurations (e.g., creating `bridge_domains/BD_Prod.yaml` with the correct links).
4. **Prune and update network files**: It outputs updated network files in the new `networks/` subfolder. All redundant, inherited metadata (like `datacenter`, `zone`, `vlan`, `bridge_domain`) is automatically pruned from individual files, leaving only `epg: <epg_name>`, the `cidr`, reservations, and allocations.
5. **Safety verification**: It automatically loads the newly generated relational database and validates it against the original database's resolved state to guarantee 100% data integrity before completing!
