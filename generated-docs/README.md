# Network Overview

## 🗺️ Directory Hierarchy Tree


- 🏢 **[DC_Frankfurt](datacenters/DC_Frankfurt.md)**
  
  - 📍 **[Trusted](zones/Trusted.md)**
    
      - 🌉 **[BD_Prod](bridge_domains/BD_Prod.md)**
        
          - 🌍 **[unassigned](environments/unassigned.md)**
            
              - 🏷️ **[EPG_App](epgs/EPG_App.md)**
                
                - 🔌 **[backend_net](networks/backend_net.md)** (`10.0.2.0/24`) — *Application Backend*
                
            
              - 🏷️ **[EPG_Web](epgs/EPG_Web.md)**
                
                - 🔌 **[example_net](networks/example_net.md)** (`10.0.0.0/24`) — *Production Web Tier*
                
            
        
    
  
  - 📍 **[Untrusted](zones/Untrusted.md)**
    
      - 🌉 **[BD_DMZ](bridge_domains/BD_DMZ.md)**
        
          - 🌍 **[unassigned](environments/unassigned.md)**
            
              - 🏷️ **[EPG_FrontEnd](epgs/EPG_FrontEnd.md)**
                
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
                
            
        
    
  


