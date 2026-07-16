# Networks Index

| Network | CIDR | EPG | VLAN | Context | Description |
| --- | --- | --- | --- | --- | --- |
| [backend_net](backend_net.md) | `10.0.2.0/24` | [EPG_App](../epgs/EPG_App.md) | 30 | `default` | Application Backend |
| [example_net](example_net.md) | `10.0.0.0/24` | [EPG_Web](../epgs/EPG_Web.md) | 10 | `default` | Production Web Tier |
| [dmz_net](dmz_net.md) | `10.0.1.0/24` | [EPG_FrontEnd](../epgs/EPG_FrontEnd.md) | 20 | `default` | Public Facing DMZ |
| [second_net](second_net.md) | `10.0.0.128/25` | None | 20 | `isolated` | Overlapping Network but not routable |
| [global-ovn-cluster](global-ovn-cluster.md) | `10.3.128.0/18` | None | None | `default` | OVN Cluster internal network |
