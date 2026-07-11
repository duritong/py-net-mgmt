import fcntl
import ipaddress
import os
from typing import List

import yaml

from .core import Allocation, Network, Reservation


def load_network_from_file(file_path: str) -> Network:
    # We open the file in read mode.
    # We could acquire a shared lock here, but for simple CLI read it's often fine.
    # To be safe, let's acquire a shared lock.
    with open(file_path, "r") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            data = yaml.safe_load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    if data is None:
        data = {}

    reservations = []
    if "reservations" in data and data["reservations"]:
        for res in data["reservations"]:
            reservations.append(
                Reservation(
                    id=str(res.get("id", "")),
                    cidr=res.get("cidr", ""),
                    comment=res.get("comment", ""),
                    allocatable=res.get("allocatable", False),
                )
            )

    allocations = []
    if "allocations" in data and data["allocations"]:
        for alloc in data["allocations"]:
            allocations.append(
                Allocation(
                    ip=alloc.get("ip"),
                    hostname=alloc.get("hostname"),
                    cidr=alloc.get("cidr"),
                    comment=alloc.get("comment"),
                )
            )

    network = Network(
        name=os.path.basename(file_path).replace(".yaml", "").replace(".yml", ""),
        cidr=data.get("cidr", "0.0.0.0/0"),
        vlan=data.get("vlan"),
        bridge_domain=data.get("bridge_domain"),
        environment=data.get("environment"),
        epg=data.get("epg"),
        default_mtu=data.get("default_mtu"),
        dns_nameservers=data.get("dns_nameservers"),
        dns_search=data.get("dns_search"),
        timeservers=data.get("timeservers"),
        static_routes=data.get("static_routes", []),
        zone=data.get("zone"),
        datacenter=data.get("datacenter"),
        routable=data.get("routable", True),
        context=data.get("context", "default"),
        description=data.get("description"),
        file_path=file_path,
        reservations=reservations,
        allocations=allocations,
        reserve_gateway=data.get("reserve_gateway", True),
        reserve_internal=data.get("reserve_internal", True),
    )
    network.validate()
    return network


def apply_hierarchy_config(networks: List[Network], directory: str):
    """
    Parse networks/hierarchy.yaml (or hierarchy.yml) and apply inheritance to networks.
    """
    hierarchy_path = None
    for f in ["hierarchy.yaml", "hierarchy.yml"]:
        p = os.path.join(directory, f)
        if os.path.exists(p):
            hierarchy_path = p
            break

    if not hierarchy_path:
        return

    with open(hierarchy_path, "r", encoding="utf-8") as f:
        try:
            config = yaml.safe_load(f)
        except Exception:
            return

    if not config or "datacenters" not in config:
        return

    net_map = {net.name: net for net in networks}

    def traverse(node, context_attrs):
        current_attrs = context_attrs.copy()
        for attr in ["timeservers", "dns_nameservers", "dns_search", "default_mtu", "routable", "context"]:
            if attr in node:
                current_attrs[attr] = node[attr]

        if "datacenters" in node:
            for dc_name, dc_node in node["datacenters"].items():
                dc_attrs = current_attrs.copy()
                dc_attrs["datacenter"] = dc_name
                traverse(dc_node, dc_attrs)
            return

        if "zones" in node:
            for zone_name, zone_node in node["zones"].items():
                zone_attrs = current_attrs.copy()
                zone_attrs["zone"] = zone_name
                traverse(zone_node, zone_attrs)
            return

        if "bridge_domains" in node:
            for bd_name, bd_node in node["bridge_domains"].items():
                bd_attrs = current_attrs.copy()
                bd_attrs["bridge_domain"] = bd_name
                traverse(bd_node, bd_attrs)
            return

        if "environments" in node:
            for env_name, env_node in node["environments"].items():
                env_attrs = current_attrs.copy()
                env_attrs["environment"] = env_name
                traverse(env_node, env_attrs)
            return

        if "epgs" in node:
            for epg_name, epg_node in node["epgs"].items():
                epg_attrs = current_attrs.copy()
                epg_attrs["epg"] = epg_name
                traverse(epg_node, epg_attrs)
            return

        if "networks" in node:
            for net_name in node["networks"]:
                if net_name in net_map:
                    apply_to_network(net_map[net_name], current_attrs)

    def apply_to_network(net: Network, attrs: dict):
        if not net.datacenter and "datacenter" in attrs:
            net.datacenter = attrs["datacenter"]
        if not net.zone and "zone" in attrs:
            net.zone = attrs["zone"]
        if not net.bridge_domain and "bridge_domain" in attrs:
            net.bridge_domain = attrs["bridge_domain"]
        if not net.environment and "environment" in attrs:
            net.environment = attrs["environment"]
        if not net.epg and "epg" in attrs:
            net.epg = attrs["epg"]

        if not net.timeservers and "timeservers" in attrs:
            net.timeservers = attrs["timeservers"]
        if not net.dns_nameservers and "dns_nameservers" in attrs:
            net.dns_nameservers = attrs["dns_nameservers"]
        if not net.dns_search and "dns_search" in attrs:
            net.dns_search = attrs["dns_search"]
        if net.default_mtu is None and "default_mtu" in attrs:
            net.default_mtu = attrs["default_mtu"]
        if "routable" in attrs and net.routable is True:
            net.routable = attrs["routable"]
        if net.context == "default" and "context" in attrs:
            net.context = attrs["context"]

    traverse(config, {})

    for net in networks:
        if net.datacenter:
            dc_node = config["datacenters"].get(net.datacenter)
            if dc_node:
                attrs = {"datacenter": net.datacenter}
                for attr in ["timeservers", "dns_nameservers", "dns_search", "default_mtu", "routable", "context"]:
                    if attr in dc_node:
                        attrs[attr] = dc_node[attr]

                if net.zone and "zones" in dc_node:
                    zone_node = dc_node["zones"].get(net.zone)
                    if zone_node:
                        attrs["zone"] = net.zone
                        for attr in [
                            "timeservers",
                            "dns_nameservers",
                            "dns_search",
                            "default_mtu",
                            "routable",
                            "context",
                        ]:
                            if attr in zone_node:
                                attrs[attr] = zone_node[attr]

                        if net.bridge_domain and "bridge_domains" in zone_node:
                            bd_node = zone_node["bridge_domains"].get(net.bridge_domain)
                            if bd_node:
                                attrs["bridge_domain"] = net.bridge_domain
                                for attr in [
                                    "timeservers",
                                    "dns_nameservers",
                                    "dns_search",
                                    "default_mtu",
                                    "routable",
                                    "context",
                                ]:
                                    if attr in bd_node:
                                        attrs[attr] = bd_node[attr]

                                if net.environment and "environments" in bd_node:
                                    env_node = bd_node["environments"].get(net.environment)
                                    if env_node:
                                        attrs["environment"] = net.environment
                                        for attr in [
                                            "timeservers",
                                            "dns_nameservers",
                                            "dns_search",
                                            "default_mtu",
                                            "routable",
                                            "context",
                                        ]:
                                            if attr in env_node:
                                                attrs[attr] = env_node[attr]

                                        if net.epg and "epgs" in env_node:
                                            epg_node = env_node["epgs"].get(net.epg)
                                            if epg_node:
                                                attrs["epg"] = net.epg
                                                for attr in [
                                                    "timeservers",
                                                    "dns_nameservers",
                                                    "dns_search",
                                                    "default_mtu",
                                                    "routable",
                                                    "context",
                                                ]:
                                                    if attr in epg_node:
                                                        attrs[attr] = epg_node[attr]

                apply_to_network(net, attrs)


def load_all_networks(directory: str) -> List[Network]:
    if is_relational_mode(directory):
        # Relational Multi-Folder Database loading
        datacenters = load_yaml_files_from_subdir(directory, "datacenters")
        zones = load_yaml_files_from_subdir(directory, "zones")
        environments = load_yaml_files_from_subdir(directory, "environments")
        bridge_domains = load_yaml_files_from_subdir(directory, "bridge_domains")
        epgs = load_yaml_files_from_subdir(directory, "epgs")

        networks = []
        net_dir = os.path.join(directory, "networks")
        for file in os.listdir(net_dir):
            if file.lower().endswith(".yaml"):  # Enforce standard .yaml extension!
                file_path = os.path.join(net_dir, file)
                networks.append(load_network_from_file(file_path))

        # Validate and apply relationships/metadata resolution cascade
        for net in networks:
            # 1. ForeignKey Integrity and Strict validations for epg
            if net.epg:
                if net.epg not in epgs:
                    raise ValueError(
                        f"ForeignKey Integrity: EPG '{net.epg}' referenced by network '{net.name}' does not exist."
                    )
                epg_data = epgs[net.epg]

                # VLAN Match check
                epg_vlan = epg_data.get("vlan")
                if net.vlan is not None and epg_vlan is not None and net.vlan != epg_vlan:
                    raise ValueError(
                        f"VLAN Match check: Network '{net.name}' defines vlan {net.vlan} "
                        f"which conflicts with EPG '{net.epg}' vlan {epg_vlan}."
                    )
                if net.vlan is None:
                    net.vlan = epg_vlan

                # Bridge Domain Match check
                epg_bd = epg_data.get("bridge_domain")
                if net.bridge_domain is not None and epg_bd is not None and net.bridge_domain != epg_bd:
                    raise ValueError(
                        f"Bridge Domain Match check: Network '{net.name}' defines bridge_domain "
                        f"'{net.bridge_domain}' which conflicts with EPG '{net.epg}' "
                        f"bridge_domain '{epg_bd}'."
                    )
                if net.bridge_domain is None:
                    net.bridge_domain = epg_bd

                # Environment Match check
                epg_env = epg_data.get("environment")
                if net.environment is not None and epg_env is not None and net.environment != epg_env:
                    raise ValueError(
                        f"Environment Match check: Network '{net.name}' defines environment "
                        f"'{net.environment}' which conflicts with EPG '{net.epg}' "
                        f"environment '{epg_env}'."
                    )
                if net.environment is None:
                    net.environment = epg_env

            # 2. Network with bridge_domain must have an EPG (User's Decision #2!)
            if net.bridge_domain is not None and net.epg is None:
                raise ValueError(
                    f"Validation Error: Network '{net.name}' defines a bridge_domain "
                    f"'{net.bridge_domain}' but does not have an epg defined."
                )

            # 3. ForeignKey Integrity and Strict validations for bridge_domain
            if net.bridge_domain:
                if net.bridge_domain not in bridge_domains:
                    raise ValueError(
                        f"ForeignKey Integrity: Bridge Domain '{net.bridge_domain}' "
                        f"referenced by network '{net.name}' does not exist."
                    )
                bd_data = bridge_domains[net.bridge_domain]

                # Datacenter Match check
                bd_dc = bd_data.get("datacenter")
                if net.datacenter is not None and bd_dc is not None and net.datacenter != bd_dc:
                    raise ValueError(
                        f"Datacenter Match check: Network '{net.name}' defines datacenter "
                        f"'{net.datacenter}' which conflicts with Bridge Domain '{net.bridge_domain}' "
                        f"datacenter '{bd_dc}'."
                    )
                if net.datacenter is None:
                    net.datacenter = bd_dc

                # Zone Match check
                bd_zone = bd_data.get("zone")
                if net.zone is not None and bd_zone is not None and net.zone != bd_zone:
                    raise ValueError(
                        f"Zone Match check: Network '{net.name}' defines zone '{net.zone}' "
                        f"which conflicts with Bridge Domain '{net.bridge_domain}' zone '{bd_zone}'."
                    )
                if net.zone is None:
                    net.zone = bd_zone

            # 4. ForeignKey Integrity for environment
            if net.environment:
                if net.environment not in environments:
                    raise ValueError(
                        f"ForeignKey Integrity: Environment '{net.environment}' "
                        f"referenced by network '{net.name}' does not exist."
                    )

            # 5. ForeignKey Integrity for datacenter
            if net.datacenter:
                if net.datacenter not in datacenters:
                    raise ValueError(
                        f"ForeignKey Integrity: Datacenter '{net.datacenter}' "
                        f"referenced by network '{net.name}' does not exist."
                    )

            # 6. ForeignKey Integrity for zone
            if net.zone:
                if net.zone not in zones:
                    raise ValueError(
                        f"ForeignKey Integrity: Zone '{net.zone}' referenced by network '{net.name}' does not exist."
                    )

            # 7. Metadata Resolution Cascade (Attribute Resolution Cascade)
            for field_name in ["timeservers", "dns_nameservers", "dns_search", "default_mtu"]:
                val = getattr(net, field_name, None)
                if val is not None:
                    continue  # Already has local override

                if net.epg and net.epg in epgs:
                    val = epgs[net.epg].get(field_name)
                    if val is not None:
                        setattr(net, field_name, val)
                        continue

                if net.environment and net.environment in environments:
                    val = environments[net.environment].get(field_name)
                    if val is not None:
                        setattr(net, field_name, val)
                        continue

                if net.bridge_domain and net.bridge_domain in bridge_domains:
                    val = bridge_domains[net.bridge_domain].get(field_name)
                    if val is not None:
                        setattr(net, field_name, val)
                        continue

                if net.zone and net.zone in zones:
                    val = zones[net.zone].get(field_name)
                    if val is not None:
                        setattr(net, field_name, val)
                        continue

                if net.datacenter and net.datacenter in datacenters:
                    val = datacenters[net.datacenter].get(field_name)
                    if val is not None:
                        setattr(net, field_name, val)
                        continue

        return networks
    else:
        # Legacy flat structure with hierarchy.yaml
        networks = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".yaml") or file.endswith(".yml"):
                    if file in ("hierarchy.yaml", "hierarchy.yml"):
                        continue
                    networks.append(load_network_from_file(os.path.join(root, file)))
        apply_hierarchy_config(networks, directory)
        return networks


def is_relational_mode(directory: str) -> bool:
    # Check if 'networks' and at least one other directory exists under the target path
    has_networks = os.path.isdir(os.path.join(directory, "networks"))
    has_others = any(
        os.path.isdir(os.path.join(directory, d))
        for d in ["epgs", "bridge_domains", "environments", "zones", "datacenters"]
    )
    return has_networks and has_others


def load_yaml_files_from_subdir(directory: str, subdir: str) -> dict:
    result = {}
    path = os.path.join(directory, subdir)
    if not os.path.isdir(path):
        return result
    for file in os.listdir(path):
        if file.lower().endswith(".yaml"):  # Enforce standard .yaml extension!
            name = os.path.splitext(file)[0]
            file_path = os.path.join(path, file)
            with open(file_path, "r", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = yaml.safe_load(f)
                except Exception:
                    data = {}
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            result[name] = data or {}
    return result


def save_network_to_file(network: Network):
    """Save network configuration back to its YAML file."""
    if not network.file_path:
        raise ValueError("Network has no file path associated with it.")

    db_dir = os.path.dirname(os.path.dirname(network.file_path))
    relational = is_relational_mode(db_dir)

    # We open the file in append mode just to get a file descriptor for locking
    # without truncating it yet.
    with open(network.file_path, "a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            lock_file.seek(0)

            # Read all full-line comments to preserve them at the top
            comments = []
            for line in lock_file:
                if line.lstrip().startswith("#"):
                    comments.append(line)

            data = {
                "cidr": str(network.cidr),
                "routable": network.routable,
                "reserve_gateway": network.reserve_gateway,
                "reserve_internal": network.reserve_internal,
            }

            if network.context != "default":
                data["context"] = network.context

            inherited_vlan = None
            inherited_bd = None
            inherited_env = None
            inherited_dc = None
            inherited_zone = None
            inherited_metadata = {"timeservers": None, "dns_nameservers": None, "dns_search": None, "default_mtu": None}

            if relational:
                # Load relational databases for this DB directory
                datacenters = load_yaml_files_from_subdir(db_dir, "datacenters")
                zones = load_yaml_files_from_subdir(db_dir, "zones")
                environments = load_yaml_files_from_subdir(db_dir, "environments")
                bridge_domains = load_yaml_files_from_subdir(db_dir, "bridge_domains")
                epgs = load_yaml_files_from_subdir(db_dir, "epgs")

                if network.epg and network.epg in epgs:
                    epg_data = epgs[network.epg]
                    inherited_vlan = epg_data.get("vlan")
                    inherited_bd = epg_data.get("bridge_domain")
                    inherited_env = epg_data.get("environment")

                    if inherited_bd and inherited_bd in bridge_domains:
                        bd_data = bridge_domains[inherited_bd]
                        inherited_dc = bd_data.get("datacenter")
                        inherited_zone = bd_data.get("zone")

                # Now resolve inherited metadata fields to see if we have overridden them
                for field_name in inherited_metadata:
                    val = None
                    if network.epg and network.epg in epgs:
                        val = epgs[network.epg].get(field_name)
                    if val is None and inherited_env and inherited_env in environments:
                        val = environments[inherited_env].get(field_name)
                    if val is None and inherited_bd and inherited_bd in bridge_domains:
                        val = bridge_domains[inherited_bd].get(field_name)
                    if val is None and inherited_zone and inherited_zone in zones:
                        val = zones[inherited_zone].get(field_name)
                    if val is None and inherited_dc and inherited_dc in datacenters:
                        val = datacenters[inherited_dc].get(field_name)
                    inherited_metadata[field_name] = val

            if relational:
                if network.epg:
                    data["epg"] = network.epg
                if network.vlan is not None and (network.epg is None or network.vlan != inherited_vlan):
                    data["vlan"] = network.vlan
                if network.bridge_domain and (network.epg is None or network.bridge_domain != inherited_bd):
                    data["bridge_domain"] = network.bridge_domain
                if network.environment and (network.epg is None or network.environment != inherited_env):
                    data["environment"] = network.environment
                if network.datacenter and (network.epg is None or network.datacenter != inherited_dc):
                    data["datacenter"] = network.datacenter
                if network.zone and (network.epg is None or network.zone != inherited_zone):
                    data["zone"] = network.zone

                # For metadata: write only if different from inherited (and not None)
                for field_name in ["timeservers", "dns_nameservers", "dns_search", "default_mtu"]:
                    val = getattr(network, field_name, None)
                    if val is not None and val != inherited_metadata[field_name]:
                        data[field_name] = val
            else:
                # Legacy flat structure direct write
                if network.vlan is not None:
                    data["vlan"] = network.vlan
                if network.bridge_domain:
                    data["bridge_domain"] = network.bridge_domain
                if network.environment:
                    data["environment"] = network.environment
                if network.epg:
                    data["epg"] = network.epg
                if network.default_mtu is not None:
                    data["default_mtu"] = network.default_mtu
                if network.dns_nameservers:
                    data["dns_nameservers"] = network.dns_nameservers
                if network.dns_search:
                    data["dns_search"] = network.dns_search
                if network.timeservers:
                    data["timeservers"] = network.timeservers
                if network.zone:
                    data["zone"] = network.zone
                if network.datacenter:
                    data["datacenter"] = network.datacenter

            if network.static_routes:
                data["static_routes"] = [{"cidr": sr.cidr, "gateway": sr.gateway} for sr in network.static_routes]
            if network.description:
                data["description"] = network.description

            if network.reservations:
                data["reservations"] = []
                for res in network.reservations:
                    res_data = {
                        "id": res.id,
                        "cidr": res.cidr,
                        "comment": res.comment,
                    }
                    if res.allocatable:
                        res_data["allocatable"] = True
                    data["reservations"].append(res_data)

            if network.allocations:
                data["allocations"] = []

                def sort_key(a):
                    if a.ip:
                        return a.ip
                    elif a.cidr:
                        try:
                            return ipaddress.ip_network(a.cidr.split("-")[0].strip(), strict=False).network_address
                        except ValueError:
                            return ipaddress.ip_address(a.cidr.split("-")[0].strip())
                    return ipaddress.ip_address("0.0.0.0")

                sorted_allocs = sorted(network.allocations, key=sort_key)

                for alloc in sorted_allocs:
                    alloc_data = {}
                    if alloc.ip:
                        alloc_data["ip"] = str(alloc.ip)
                        if alloc.hostname:
                            alloc_data["hostname"] = alloc.hostname
                        if alloc.comment:
                            alloc_data["comment"] = alloc.comment
                    elif alloc.cidr:
                        alloc_data["cidr"] = alloc.cidr
                        alloc_data["comment"] = alloc.comment
                    data["allocations"].append(alloc_data)

            # Now write the data back, truncating the file
            lock_file.seek(0)
            lock_file.truncate()

            # Write comments first
            for comment in comments:
                lock_file.write(comment)

            # Dump YAML
            yaml.dump(data, lock_file, sort_keys=False)

        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
