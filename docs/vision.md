# net-mgmt architecture vision

This document acts as a high level architecture vision to document:

* target audience
* the goals and non-goals of the library

## Target audience

The library should be useful to SRE / Platform teams that need to consume network data within their automation engines or templates. Such a team deploys infrastructure within a larger network and into multiple datacenters, environments and security zones.

For the context of a SRE / Platform team a network is a certain network prefix. which they are using to deploy their services in to. Typically, such networks are getting assigned from the central networking team, that is responsible to distribute and manage networks within an organization.

The SRE / Platform are using these networks to deploy their infrastructure into. For that they need to keep an inventory of these networks, as well as the metadata of these networks. Such metadata can for example be, how they might be physically layed out (Bridge Domains, EPGs/VLANs) or also service definitions such as DNS or timeservers.

While organizing the assigned networks for their use-cases, some networks might get subnet ranges assigned for DHCP, other subnet ranges are pre-defined for grouping purposes, such as ranges for static IP addressing of hosts or to be consumed to setup services such as load balancers.

The data living within net-mgmt should only be authorative within the team itself for their use-cases and not act as data source for further teams. Eventually, that data might also be sourced out of central networking CMDBs such as NetBox and exported to them. Essentially, acting as glueing data source between the organization and the teams automation engine, so that these tools must not depend on the availability of external services, such as the central CMDB.

The SRE / Platform team typically stores the net-mgmt database within a git repository, where changes can easily be reviewed, approved and tracked over time.

The net-mgmt library and its data structure is therefore designed around the use cases for a SRE / Platform team, which might be less suitable for other use-cases such as networking teams or a CMDB.

The design of net-mgmt helps SRE / Platform teams to easily organize their view onto how they are consuming networking information within their organization and optimize best for the use within their tooling. This deliberately means net-mgmt might leave out technical details that are important from a networking perspective, but irrelevant to the use cases for the SRE / Platform team.

The net-mgmt library helps to de-duplicate redundant networking information (such as IP addresses), be providing means to query it from net-mgmt. Since for example a backend-ip might be used in multiple templates, net-mgmt can act as the single data source for that ip address, which can be looked up from multiple places through an identifier. Additionally, it can act as team-local ip registry, where automation tools can automatically allocate new ip addresses if they are for example scaling out.

## Goals

* Provides a view on networks that SRE / Platform teams are consuming
* Easy consumable by humans and easily applying to gitops workflows
* Validates the stored data and ensures network usage consistency
* Avoids redundant data / information within the source
* Provides aggregated views through a cli, easily consumable and verifiable by humas
* Provides means to generate network documentation and share information about hte current usage
* Provides interfaces for other automation tools
* Provides jinja2 filters to consume the data in net-mgmt within templates
* Supports thread-safe, concurrent local allocations to support parallel access and workflows.
* Keeps data structures and YAML schemas loosely aligned with typical NetBox exports, making it trivial to write synchronization scripts that cache NetBox datasets into local Git repositories.
* Provides standard programmatic and CLI routines for de-allocating/pruning obsolete hostnames to maintain a clean database and prevent IP exhaustion.
* Provides environment portability, allowing SREs to easily swap different network directories (e.g. Lab, Staging, Prod) at runtime without altering template code or automation filters.
* Preserves human readability, ordering, and inline comments in YAML definitions even when modified programmatically by automation tools or the CLI.


## Non goals

* net-mgmt is not a tool to organize your overall view on the network. Use NetBox for this.
* net-mgmt is not for networking teams or a central CMDB. Use NetBox for this.
* net-mgmt's view on the network is not multi-facet.
* "net-mgmt does not monitor or discover the active network state (e.g. ICMP pinging, SNMP polling). It strictly holds the team's declarative intent of what has been allocated."
* "net-mgmt does not implement multi-tenant ACLs or permissions. Access control, scope boundaries, and write restrictions are delegated entirely to native Git repository configurations, branch protections, and PR workflows."
