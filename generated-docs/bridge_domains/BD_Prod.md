# Bridge Domain: BD_Prod

## Properties
- **Datacenter**: [DC_Frankfurt](../datacenters/DC_Frankfurt.md)
- **Zone**: [Trusted](../zones/Trusted.md)


## Associated Subnets
| Network Name | CIDR | Context | Description |
| --- | --- | --- | --- |
| [backend_net](../networks/backend_net.md) | `10.0.2.0/24` | `default` | Application Backend |
| [corp-app](../networks/corp-app.md) | `10.10.1.0/24` | `default` | Corporate Application Tier |
| [corp-db](../networks/corp-db.md) | `10.10.2.0/24` | `default` | Corporate Database Tier |
| [corp-web](../networks/corp-web.md) | `10.10.0.0/24` | `default` | Corporate Web Tier |
| [example_net](../networks/example_net.md) | `10.0.0.0/24` | `default` | Production Web Tier |
