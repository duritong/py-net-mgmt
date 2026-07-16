# backend_net

## Settings
- **CIDR**: `10.0.2.0/24`
- **Context**: `default`
- **Description**: Application Backend
- **VLAN**: `30`
- **Bridge Domain**: [BD_Prod](../bridge_domains/BD_Prod.md)
- **Environment**: `None`
- **EPG**: [EPG_App](../epgs/EPG_App.md)
- **MTU**: `None`

- **DNS Nameservers**: `None`
- **DNS Search**: `None`
- **Timeservers**: `None`


- **Static Routes**: `None`


- **Zone**: [Trusted](../zones/Trusted.md)
- **Datacenter**: [DC_Frankfurt](../datacenters/DC_Frankfurt.md)
- **Routable**: `True`
- **Reserve Gateway**: `False`
- **Reserve Internal**: `True`

## Reservations
| ID | CIDR | Comment | Allocatable | Allocations | Usage |
| --- | --- | --- | --- | --- | --- |
| custom-gw | 10.0.2.1/32 | Custom Gateway Config | False | 0 | 0/1 (0.0%) |
| app-cluster | 10.0.2.20-10.0.2.30 | App Server Cluster | True | 2 | 2/11 (18.2%) |
| db-vip | 10.0.2.50/32 | Database VIP | False | 0 | 0/1 (0.0%) |
| dynamic-pool | 10.0.2.128/26 | Dynamic Allocations | True | 1 | 1/64 (50.0%) |
| sys-network | 10.0.2.0 | network address | False | 0 | 0/1 (0.0%) |
| sys-broadcast | 10.0.2.255 | broadcast address | False | 0 | 0/1 (0.0%) |
| sys-internal | 10.0.2.2-10.0.2.5 | network internal | False | 0 | 0/4 (0.0%) |
## Allocations
| IP/CIDR | Hostname/Comment |
| --- | --- |
| 10.0.2.20 | app-01 |
| 10.0.2.21 | app-02 |
| 10.0.2.128/27 | Kubernetes Pod Subnet |
## Unreserved Ranges
- `10.0.2.6 - 10.0.2.19`
- `10.0.2.31 - 10.0.2.49`
- `10.0.2.51 - 10.0.2.127`
- `10.0.2.192 - 10.0.2.255`
