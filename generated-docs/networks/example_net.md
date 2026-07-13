# example_net

## Settings
- **CIDR**: `10.0.0.0/24`
- **Context**: `default`
- **Description**: Production Web Tier
- **VLAN**: `10`
- **Bridge Domain**: [BD_Prod](../bridge_domains/BD_Prod.md)
- **Environment**: `None`
- **EPG**: [EPG_Web](../epgs/EPG_Web.md)
- **MTU**: `None`

- **DNS Nameservers**: `None`
- **DNS Search**: `None`
- **Timeservers**: `None`


- **Static Routes**: `None`


- **Zone**: [Trusted](../zones/Trusted.md)
- **Datacenter**: [DC_Frankfurt](../datacenters/DC_Frankfurt.md)
- **Routable**: `True`
- **Reserve Gateway**: `False`
- **Reserve Internal**: `False`

## Reservations

| ID | CIDR | Comment | Allocatable | Allocations | Usage |
| --- | --- | --- | --- | --- | --- |


| gw | 10.0.0.1/32 | Gateway | False | 0 | 0/1 (0.0%) |


| vip-lb | 10.0.0.10/32 | Load Balancer VIP | False | 0 | 0/1 (0.0%) |


| pool-01 | 10.0.0.20-10.0.0.30 | Reserved Pool | True | 2 | 2/11 (27.3%) |


| sys-network | 10.0.0.0 | network address | False | 0 | 0/1 (0.0%) |


| sys-broadcast | 10.0.0.255 | broadcast address | False | 0 | 0/1 (0.0%) |




## Allocations
| IP/CIDR | Hostname/Comment |
| --- | --- |


| 10.0.0.20 | host-01 |



| 10.0.0.25-10.0.0.26 | Management Cluster |






## Unreserved Ranges

- `10.0.0.2 - 10.0.0.9`

- `10.0.0.11 - 10.0.0.19`

- `10.0.0.31 - 10.0.0.255`

