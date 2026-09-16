# Network Overview


| Topology / Network | CIDR | EPG | VLAN | Context | Description |
| :--- | :--- | :--- | :---: | :---: | :--- |
| 🏢 **[DC_Frankfurt](datacenters/DC_Frankfurt.md)** |  |  |  |  |  |
| ├── 📍 **[Trusted](zones/Trusted.md)** |  |  |  |  |  |
| │   ├── 📦 [**corp-aggregate**](networks/corp-aggregate.md) | `10.10.0.0/22` | *Aggregate* | — | `default` | Corporate Service Aggregate Network (/22 block) |
| │   │   ├── 🔌 [corp-web](networks/corp-web.md) | `10.10.0.0/24` | [EPG_Web](epgs/EPG_Web.md) | 10 | `default` | Corporate Web Tier |
| │   │   ├── 🔌 [corp-app](networks/corp-app.md) | `10.10.1.0/24` | [EPG_App](epgs/EPG_App.md) | 30 | `default` | Corporate Application Tier |
| │   │   ├── 🔌 [corp-db](networks/corp-db.md) | `10.10.2.0/24` | [EPG_DB](epgs/EPG_DB.md) | 40 | `default` | Corporate Database Tier |
| │   │   └── 🔌 [corp-dmz](networks/corp-dmz.md) | `10.10.3.0/24` | [EPG_FrontEnd](epgs/EPG_FrontEnd.md) | 20 | `default` | Corporate DMZ Services |
| │   └── 🌉 **[BD_Prod](bridge_domains/BD_Prod.md)** |  |  |  |  |  |
| │       ├── 🔌 [backend_net](networks/backend_net.md) | `10.0.2.0/24` | [EPG_App](epgs/EPG_App.md) | 30 | `default` | Application Backend |
| │       └── 🔌 [example_net](networks/example_net.md) | `10.0.0.0/24` | [EPG_Web](epgs/EPG_Web.md) | 10 | `default` | Production Web Tier |
| ├── 📍 **[Untrusted](zones/Untrusted.md)** |  |  |  |  |  |
| │   └── 🌉 **[BD_DMZ](bridge_domains/BD_DMZ.md)** |  |  |  |  |  |
| │       └── 🔌 [dmz_net](networks/dmz_net.md) | `10.0.1.0/24` | [EPG_FrontEnd](epgs/EPG_FrontEnd.md) | 20 | `default` | Public Facing DMZ |
| └── 🔌 [second_net](networks/second_net.md) | `10.0.0.128/25` | None | 20 | `isolated` | Overlapping Network but not routable |
| 🏢 **[global](datacenters/global.md)** |  |  |  |  |  |
| └── 📍 **[global](zones/global.md)** |  |  |  |  |  |
|     └── 🔌 [global-ovn-cluster](networks/global-ovn-cluster.md) | `10.3.128.0/18` | None | — | `default` | OVN Cluster internal network |



