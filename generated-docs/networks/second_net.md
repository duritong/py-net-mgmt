# second_net

## Settings
- **CIDR**: `10.0.0.128/25`



- **Context**: `isolated`
- **Description**: Overlapping Network but not routable
- **VLAN**: `20`
- **Bridge Domain**: `None`
- **Environment**: `None`
- **EPG**: `None`
- **MTU**: `None`

- **DNS Nameservers**: `None`
- **DNS Search**: `None`
- **Timeservers**: `None`


- **Static Routes**: `None`


- **Zone**: `None`
- **Datacenter**: [DC_Frankfurt](../datacenters/DC_Frankfurt.md)
- **Routable**: `False`
- **Reserve Gateway**: `True`
- **Reserve Internal**: `True`
- **Reserve Internal Until**: `6`

## Reservations
| ID | CIDR | Comment | Allocatable | Allocations | Usage |
| --- | --- | --- | --- | --- | --- |
| sys-network | 10.0.0.128 | network address | False | 0 | 0/1 (0.0%) |
| sys-broadcast | 10.0.0.255 | broadcast address | False | 0 | 0/1 (0.0%) |
| sys-gateway | 10.0.0.129 | network internal | False | 0 | 0/1 (0.0%) |
| sys-internal | 10.0.0.130-10.0.0.134 | network internal | False | 0 | 0/5 (0.0%) |
## Unreserved Ranges
- `10.0.0.135 - 10.0.0.255`
