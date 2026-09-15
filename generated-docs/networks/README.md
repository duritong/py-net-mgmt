# Networks Index

| Network | CIDR | EPG | VLAN | Context | Description |
| --- | --- | --- | --- | --- | --- |
| [backend_net](backend_net.md) | `10.0.2.0/24` | [EPG_App](../epgs/EPG_App.md) | 30 | `default` | Application Backend |
| [corp-app](corp-app.md) | `10.10.1.0/24` | [EPG_App](../epgs/EPG_App.md) | 30 | `default` | Corporate Application Tier |
| [corp-db](corp-db.md) | `10.10.2.0/24` | [EPG_DB](../epgs/EPG_DB.md) | 40 | `default` | Corporate Database Tier |
| [corp-web](corp-web.md) | `10.10.0.0/24` | [EPG_Web](../epgs/EPG_Web.md) | 10 | `default` | Corporate Web Tier |
| [example_net](example_net.md) | `10.0.0.0/24` | [EPG_Web](../epgs/EPG_Web.md) | 10 | `default` | Production Web Tier |
| [corp-aggregate](corp-aggregate.md) | `10.10.0.0/22` | *Aggregate* | None | `default` | Corporate Service Aggregate Network (/22 block) |
| [corp-dmz](corp-dmz.md) | `10.10.3.0/24` | [EPG_FrontEnd](../epgs/EPG_FrontEnd.md) | 20 | `default` | Corporate DMZ Services |
| [dmz_net](dmz_net.md) | `10.0.1.0/24` | [EPG_FrontEnd](../epgs/EPG_FrontEnd.md) | 20 | `default` | Public Facing DMZ |
| [second_net](second_net.md) | `10.0.0.128/25` | None | 20 | `isolated` | Overlapping Network but not routable |
| [global-ovn-cluster](global-ovn-cluster.md) | `10.3.128.0/18` | None | None | `default` | OVN Cluster internal network |
