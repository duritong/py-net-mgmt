# corp-dmz

## Settings
- **CIDR**: `10.10.3.0/24`
- **Parent Aggregate**: [corp-aggregate](corp-aggregate.md) (`10.10.0.0/22`)
- **Context**: `default`
- **Description**: Corporate DMZ Services
- **VLAN**: `20`
- **Bridge Domain**: [BD_DMZ](../bridge_domains/BD_DMZ.md)
- **Environment**: `None`
- **EPG**: [EPG_FrontEnd](../epgs/EPG_FrontEnd.md)
- **MTU**: `None`
- **DNS Nameservers**: `None`
- **DNS Search**: `None`
- **Timeservers**: `None`
- **Static Routes**: `None`
- **Zone**: [Untrusted](../zones/Untrusted.md)
- **Datacenter**: [DC_Frankfurt](../datacenters/DC_Frankfurt.md)
- **Routable**: `True`
- **Reserve Gateway**: `True`
- **Reserve Internal**: `True`
- **Reserve Internal Until**: `6`

## Reservations
| ID | CIDR | Comment | Allocatable | Allocations | Usage |
| --- | --- | --- | --- | --- | --- |
| sys-network | 10.10.3.0 | network address | False | 0 | 0/1 (0.0%) |
| sys-broadcast | 10.10.3.255 | broadcast address | False | 0 | 0/1 (0.0%) |
| sys-gateway | 10.10.3.1 | network internal | False | 0 | 0/1 (0.0%) |
| sys-internal | 10.10.3.2-10.10.3.6 | network internal | False | 0 | 0/5 (0.0%) |


## Unreserved Ranges
- `10.10.3.7 - 10.10.3.255`
