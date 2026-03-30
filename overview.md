# Network Overview

| Name | CIDR | VLAN | Bridge Domain | EPG | Zone | Datacenter | Description |
| --- | --- | --- | --- | --- | --- | --- | --- |
| example_net | 10.0.0.0/24 | 10 | BD_Prod | EPG_Web | Trusted | DC_Frankfurt | Production Web Tier |
| second_net | 10.0.0.128/25 | 20 | None | None |  | DC_Frankfurt | Overlapping Network but not routable |
| dmz_net | 10.0.1.0/24 | 20 | BD_DMZ | EPG_FrontEnd | Untrusted | DC_Frankfurt | Public Facing DMZ |
| backend_net | 10.0.2.0/24 | 30 | BD_Prod | EPG_App | Trusted | DC_Frankfurt | Application Backend |

# Network Details

## example_net

### Settings

- **CIDR**: `10.0.0.0/24`
- **Description**: Production Web Tier
- **VLAN**: `10`
- **Bridge Domain**: `BD_Prod`
- **EPG**: `EPG_Web`
- **Zone**: `Trusted`
- **Datacenter**: `DC_Frankfurt`
- **Routable**: `True`
- **Reserve Gateway**: `False`
- **Reserve Internal**: `False`

### Reservations

| ID | CIDR | Comment | Allocatable | Allocations | Usage |
| --- | --- | --- | --- | --- | --- |
| sys-network | 10.0.0.0 | network address | False | 0 | 0/1 (0.0%) |
| gw | 10.0.0.1/32 | Gateway | False | 0 | 0/1 (0.0%) |
| vip-lb | 10.0.0.10/32 | Load Balancer VIP | False | 0 | 0/1 (0.0%) |
| pool-01 | 10.0.0.20-10.0.0.30 | Reserved Pool | True | 2 | 2/11 (27.3%) |
| sys-broadcast | 10.0.0.255 | broadcast address | False | 0 | 0/1 (0.0%) |

### Allocations

| IP/CIDR | Hostname/Comment |
| --- | --- |
| 10.0.0.20 | host-01 |
| 10.0.0.25-10.0.0.26 | Management Cluster |

### Unreserved Ranges

- `10.0.0.2/31`
- `10.0.0.4/30`
- `10.0.0.8/31`
- `10.0.0.11/32`
- `10.0.0.12/30`
- `10.0.0.16/30`
- `10.0.0.31/32`
- `10.0.0.32/27`
- `10.0.0.64/26`
- `10.0.0.128/26`
- `10.0.0.192/27`
- `10.0.0.224/28`
- `10.0.0.240/29`
- `10.0.0.248/30`
- `10.0.0.252/31`
- `10.0.0.254/32`

## second_net

### Settings

- **CIDR**: `10.0.0.128/25`
- **Description**: Overlapping Network but not routable
- **VLAN**: `20`
- **Bridge Domain**: `None`
- **EPG**: `None`
- **Zone**: `None`
- **Datacenter**: `DC_Frankfurt`
- **Routable**: `False`
- **Reserve Gateway**: `True`
- **Reserve Internal**: `True`

### Reservations

| ID | CIDR | Comment | Allocatable | Allocations | Usage |
| --- | --- | --- | --- | --- | --- |
| sys-network | 10.0.0.128 | network address | False | 0 | 0/1 (0.0%) |
| sys-gateway | 10.0.0.129 | network internal | False | 0 | 0/1 (0.0%) |
| sys-internal | 10.0.0.130-10.0.0.133 | network internal | False | 0 | 0/4 (0.0%) |
| sys-broadcast | 10.0.0.255 | broadcast address | False | 0 | 0/1 (0.0%) |

### Unreserved Ranges

- `10.0.0.134/31`
- `10.0.0.136/29`
- `10.0.0.144/28`
- `10.0.0.160/27`
- `10.0.0.192/27`
- `10.0.0.224/28`
- `10.0.0.240/29`
- `10.0.0.248/30`
- `10.0.0.252/31`
- `10.0.0.254/32`

## dmz_net

### Settings

- **CIDR**: `10.0.1.0/24`
- **Description**: Public Facing DMZ
- **VLAN**: `20`
- **Bridge Domain**: `BD_DMZ`
- **EPG**: `EPG_FrontEnd`
- **Zone**: `Untrusted`
- **Datacenter**: `DC_Frankfurt`
- **Routable**: `True`
- **Reserve Gateway**: `True`
- **Reserve Internal**: `True`

### Reservations

| ID | CIDR | Comment | Allocatable | Allocations | Usage |
| --- | --- | --- | --- | --- | --- |
| sys-network | 10.0.1.0 | network address | False | 0 | 0/1 (0.0%) |
| sys-gateway | 10.0.1.1 | network internal | False | 0 | 0/1 (0.0%) |
| sys-internal | 10.0.1.2-10.0.1.5 | network internal | False | 0 | 0/4 (0.0%) |
| server-pool | 10.0.1.10-10.0.1.50 | Web Server Pool | True | 2 | 2/41 (4.9%) |
| sys-broadcast | 10.0.1.255 | broadcast address | False | 0 | 0/1 (0.0%) |

### Allocations

| IP/CIDR | Hostname/Comment |
| --- | --- |
| 10.0.1.10 | web-dmz-01 |
| 10.0.1.11 | web-dmz-02 |

### Unreserved Ranges

- `10.0.1.6/31`
- `10.0.1.8/31`
- `10.0.1.51/32`
- `10.0.1.52/30`
- `10.0.1.56/29`
- `10.0.1.64/26`
- `10.0.1.128/26`
- `10.0.1.192/27`
- `10.0.1.224/28`
- `10.0.1.240/29`
- `10.0.1.248/30`
- `10.0.1.252/31`
- `10.0.1.254/32`

## backend_net

### Settings

- **CIDR**: `10.0.2.0/24`
- **Description**: Application Backend
- **VLAN**: `30`
- **Bridge Domain**: `BD_Prod`
- **EPG**: `EPG_App`
- **Zone**: `Trusted`
- **Datacenter**: `DC_Frankfurt`
- **Routable**: `True`
- **Reserve Gateway**: `False`
- **Reserve Internal**: `True`

### Reservations

| ID | CIDR | Comment | Allocatable | Allocations | Usage |
| --- | --- | --- | --- | --- | --- |
| sys-network | 10.0.2.0 | network address | False | 0 | 0/1 (0.0%) |
| custom-gw | 10.0.2.1/32 | Custom Gateway Config | False | 0 | 0/1 (0.0%) |
| sys-internal | 10.0.2.2-10.0.2.5 | network internal | False | 0 | 0/4 (0.0%) |
| app-cluster | 10.0.2.20-10.0.2.30 | App Server Cluster | True | 2 | 2/11 (18.2%) |
| db-vip | 10.0.2.50/32 | Database VIP | False | 0 | 0/1 (0.0%) |
| dynamic-pool | 10.0.2.128/26 | Dynamic Allocations | True | 1 | 1/64 (50.0%) |
| sys-broadcast | 10.0.2.255 | broadcast address | False | 0 | 0/1 (0.0%) |

### Allocations

| IP/CIDR | Hostname/Comment |
| --- | --- |
| 10.0.2.20 | app-01 |
| 10.0.2.21 | app-02 |
| 10.0.2.128/27 | Kubernetes Pod Subnet |

### Unreserved Ranges

- `10.0.2.6/31`
- `10.0.2.8/29`
- `10.0.2.16/30`
- `10.0.2.31/32`
- `10.0.2.32/28`
- `10.0.2.48/31`
- `10.0.2.51/32`
- `10.0.2.52/30`
- `10.0.2.56/29`
- `10.0.2.64/26`
- `10.0.2.192/27`
- `10.0.2.224/28`
- `10.0.2.240/29`
- `10.0.2.248/30`
- `10.0.2.252/31`
- `10.0.2.254/32`
