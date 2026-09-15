# Network Overview

## 🗺️ Directory Hierarchy Tree


- 🏢 **[DC_Frankfurt](datacenters/DC_Frankfurt.md)**
  
  - 📍 **[Trusted](zones/Trusted.md)**
    
      - 🌉 **[BD_Prod](bridge_domains/BD_Prod.md)**
        
          - 🌍 **[unassigned](environments/unassigned.md)**
            
              - 🏷️ **[EPG_App](epgs/EPG_App.md)**
                
                - 🔌 **[backend_net](networks/backend_net.md)** (`10.0.2.0/24`) — *Application Backend*
                
                - 🔌 **[corp-app](networks/corp-app.md)** (`10.10.1.0/24`) — *Corporate Application Tier*
                
            
              - 🏷️ **[EPG_DB](epgs/EPG_DB.md)**
                
                - 🔌 **[corp-db](networks/corp-db.md)** (`10.10.2.0/24`) — *Corporate Database Tier*
                
            
              - 🏷️ **[EPG_Web](epgs/EPG_Web.md)**
                
                - 🔌 **[corp-web](networks/corp-web.md)** (`10.10.0.0/24`) — *Corporate Web Tier*
                
                - 🔌 **[example_net](networks/example_net.md)** (`10.0.0.0/24`) — *Production Web Tier*
                
            
        
    
  
  - 📍 **[Untrusted](zones/Untrusted.md)**
    
      - 🌉 **[BD_DMZ](bridge_domains/BD_DMZ.md)**
        
          - 🌍 **[unassigned](environments/unassigned.md)**
            
              - 🏷️ **[EPG_FrontEnd](epgs/EPG_FrontEnd.md)**
                
                - 🔌 **[corp-dmz](networks/corp-dmz.md)** (`10.10.3.0/24`) — *Corporate DMZ Services*
                
                - 🔌 **[dmz_net](networks/dmz_net.md)** (`10.0.1.0/24`) — *Public Facing DMZ*
                
            
        
    
  
  - 📍 **[unassigned](zones/unassigned.md)**
    
      - 🌉 **[unassigned](bridge_domains/unassigned.md)**
        
          - 🌍 **[unassigned](environments/unassigned.md)**
            
              - 🏷️ **[unassigned](epgs/unassigned.md)**
                
                - 🔌 **[second_net](networks/second_net.md)** (`10.0.0.128/25`) — *Overlapping Network but not routable*
                
            
        
    
  

- 🏢 **[global](datacenters/global.md)**
  
  - 📍 **[global](zones/global.md)**
    
      - 🌉 **[unassigned](bridge_domains/unassigned.md)**
        
          - 🌍 **[unassigned](environments/unassigned.md)**
            
              - 🏷️ **[unassigned](epgs/unassigned.md)**
                
                - 🔌 **[global-ovn-cluster](networks/global-ovn-cluster.md)** (`10.3.128.0/18`) — *OVN Cluster internal network*
                
            
        
    
  





---

## 📦 Aggregate Networks
| Aggregate Network | CIDR | Subnets | Context | Description |
| --- | --- | --- | --- | --- |
| [corp-aggregate](networks/corp-aggregate.md) | `10.10.0.0/22` | 4 subnets | `default` | Corporate Service Aggregate Network (/22 block) |

