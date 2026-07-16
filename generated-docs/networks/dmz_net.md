# dmz_net

## Settings
- **CIDR**: `10.0.1.0/24`
- **Context**: `default`
- **Description**: Public Facing DMZ
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

## Reservations

| ID | CIDR | Comment | Allocatable | Allocations | Usage |
| --- | --- | --- | --- | --- | --- |
| server-pool | 10.0.1.10-10.0.1.50 | Web Server Pool | True | 2 | 2/41 (4.9%) |
| sys-network | 10.0.1.0 | network address | False | 0 | 0/1 (0.0%) |
| sys-broadcast | 10.0.1.255 | broadcast address | False | 0 | 0/1 (0.0%) |
| sys-gateway | 10.0.1.1 | network internal | False | 0 | 0/1 (0.0%) |
| sys-internal | 10.0.1.2-10.0.1.5 | network internal | False | 0 | 0/4 (0.0%) |




## Allocations
| IP/CIDR | Hostname/Comment |
| --- | --- |
| 10.0.1.10 | web-dmz-01 |
| 10.0.1.11 | web-dmz-02 |





## Unreserved Ranges
- `10.0.1.6 - 10.0.1.9`
- `10.0.1.51 - 10.0.1.255`

