# corp-aggregate

## Settings
- **CIDR**: `10.10.0.0/22`
- **Aggregate Network**: True


- **Context**: `default`
- **Description**: Corporate Service Aggregate Network (/22 block)
- **VLAN**: `None`
- **Bridge Domain**: `None`
- **Environment**: `None`
- **EPG**: `None`
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
- **Reserve Internal Until**: `6`

## Reservations
_No reservations._
## Unreserved Ranges
- `10.10.0.0 - 10.10.3.255`



## Sub-Prefixes (Subnets)
| Subnet | CIDR | EPG | VLAN | Bridge Domain | Description |
| --- | --- | --- | --- | --- | --- |
| [corp-app](corp-app.md) | `10.10.1.0/24` | [EPG_App](../epgs/EPG_App.md) | 30 | [BD_Prod](../bridge_domains/BD_Prod.md) | Corporate Application Tier |
| [corp-db](corp-db.md) | `10.10.2.0/24` | [EPG_DB](../epgs/EPG_DB.md) | 40 | [BD_Prod](../bridge_domains/BD_Prod.md) | Corporate Database Tier |
| [corp-web](corp-web.md) | `10.10.0.0/24` | [EPG_Web](../epgs/EPG_Web.md) | 10 | [BD_Prod](../bridge_domains/BD_Prod.md) | Corporate Web Tier |
| [corp-dmz](corp-dmz.md) | `10.10.3.0/24` | [EPG_FrontEnd](../epgs/EPG_FrontEnd.md) | 20 | [BD_DMZ](../bridge_domains/BD_DMZ.md) | Corporate DMZ Services |




