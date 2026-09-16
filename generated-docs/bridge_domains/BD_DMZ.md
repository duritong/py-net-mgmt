# Bridge Domain: BD_DMZ

## Properties
- **Datacenter**: [DC_Frankfurt](../datacenters/DC_Frankfurt.md)
- **Zone**: [Untrusted](../zones/Untrusted.md)

## Associated Subnets
| Network Name | CIDR | Context | Description |
| --- | --- | --- | --- |
| [corp-dmz](../networks/corp-dmz.md) | `10.10.3.0/24` | `default` | Corporate DMZ Services |
| [dmz_net](../networks/dmz_net.md) | `10.0.1.0/24` | `default` | Public Facing DMZ |
