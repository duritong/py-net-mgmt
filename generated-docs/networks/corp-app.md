# corp-app

## Settings
- **CIDR**: `10.10.1.0/24`
- **Parent Aggregate**: [corp-aggregate](corp-aggregate.md) (`10.10.0.0/22`)
- **Context**: `default`
- **Description**: Corporate Application Tier
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
- **Reserve Gateway**: `True`
- **Reserve Internal**: `True`
- **Reserve Internal Until**: `6`

## Reservations
| ID | CIDR | Comment | Allocatable | Allocations | Usage |
| --- | --- | --- | --- | --- | --- |
| sys-network | 10.10.1.0 | network address | False | 0 | 0/1 (0.0%) |
| sys-broadcast | 10.10.1.255 | broadcast address | False | 0 | 0/1 (0.0%) |
| sys-gateway | 10.10.1.1 | network internal | False | 0 | 0/1 (0.0%) |
| sys-internal | 10.10.1.2-10.10.1.6 | network internal | False | 0 | 0/5 (0.0%) |


## Unreserved Ranges
- `10.10.1.7 - 10.10.1.255`
