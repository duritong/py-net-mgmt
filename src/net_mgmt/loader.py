import fcntl
import ipaddress
import os
from typing import List

import yaml

from .core import Allocation, DatabaseValidationError, Network, Reservation


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
        reserve_internal_until=data.get("reserve_internal_until", 6),
    )
    network.validate()
    return network


def load_all_networks(directory: str) -> List[Network]:
    errors = []
    if not is_relational_mode(directory):
        raise DatabaseValidationError(
            ["Database is not in Relational Multi-Folder format (networks/ folder is required)."]
        )

    if os.path.isdir(os.path.join(directory, "networks")):
        db_dir = directory
        net_dir = os.path.join(directory, "networks")
    else:
        db_dir = os.path.dirname(directory)
        net_dir = directory

    # Relational Multi-Folder Database loading
    datacenters = load_yaml_files_from_subdir(db_dir, "datacenters")
    zones = load_yaml_files_from_subdir(db_dir, "zones")
    environments = load_yaml_files_from_subdir(db_dir, "environments")
    bridge_domains = load_yaml_files_from_subdir(db_dir, "bridge_domains")
    epgs = load_yaml_files_from_subdir(db_dir, "epgs")

    networks = []
    for file in os.listdir(net_dir):
        if file.lower().endswith(".yaml"):  # Enforce standard .yaml extension!
            file_path = os.path.join(net_dir, file)
            try:
                networks.append(load_network_from_file(file_path))
            except DatabaseValidationError as e:
                errors.extend(e.errors)
            except ValueError as e:
                errors.append(f"[{file}] {e}")

    # Validate and apply relationships/metadata resolution cascade
    for net in networks:
        # 1. ForeignKey Integrity and Strict validations for epg
        if net.epg:
            if net.epg not in epgs:
                errors.append(
                    f"ForeignKey Integrity: EPG '{net.epg}' referenced by network '{net.name}' does not exist."
                )
                continue
            epg_data = epgs[net.epg]

            # VLAN Match check
            epg_vlan = epg_data.get("vlan")
            if net.vlan is not None and epg_vlan is not None and net.vlan != epg_vlan:
                errors.append(
                    f"VLAN Match check: Network '{net.name}' defines vlan {net.vlan} "
                    f"which conflicts with EPG '{net.epg}' vlan {epg_vlan}."
                )
            if net.vlan is None:
                net.vlan = epg_vlan

            # Bridge Domain Match check
            epg_bd = epg_data.get("bridge_domain")
            if net.bridge_domain is not None and epg_bd is not None and net.bridge_domain != epg_bd:
                errors.append(
                    f"Bridge Domain Match check: Network '{net.name}' defines bridge_domain "
                    f"'{net.bridge_domain}' which conflicts with EPG '{net.epg}' "
                    f"bridge_domain '{epg_bd}'."
                )
            if net.bridge_domain is None:
                net.bridge_domain = epg_bd

            # Environment Match check
            epg_env = epg_data.get("environment")
            if net.environment is not None and epg_env is not None and net.environment != epg_env:
                errors.append(
                    f"Environment Match check: Network '{net.name}' defines environment "
                    f"'{net.environment}' which conflicts with EPG '{net.epg}' "
                    f"environment '{epg_env}'."
                )
            if net.environment is None:
                net.environment = epg_env

        # 2. Network with bridge_domain must have an EPG (User's Decision #2!)
        if net.bridge_domain is not None and net.epg is None:
            errors.append(
                f"Validation Error: Network '{net.name}' defines a bridge_domain "
                f"'{net.bridge_domain}' but does not have an epg defined."
            )

        # 3. ForeignKey Integrity and Strict validations for bridge_domain
        if net.bridge_domain:
            if net.bridge_domain not in bridge_domains:
                errors.append(
                    f"ForeignKey Integrity: Bridge Domain '{net.bridge_domain}' "
                    f"referenced by network '{net.name}' does not exist."
                )
                continue
            bd_data = bridge_domains[net.bridge_domain]

            # Datacenter Match check
            bd_dc = bd_data.get("datacenter")
            if net.datacenter is not None and bd_dc is not None and net.datacenter != bd_dc:
                errors.append(
                    f"Datacenter Match check: Network '{net.name}' defines datacenter "
                    f"'{net.datacenter}' which conflicts with Bridge Domain '{net.bridge_domain}' "
                    f"datacenter '{bd_dc}'."
                )
            if net.datacenter is None:
                net.datacenter = bd_dc

            # Zone Match check
            bd_zone = bd_data.get("zone")
            if net.zone is not None and bd_zone is not None and net.zone != bd_zone:
                errors.append(
                    f"Zone Match check: Network '{net.name}' defines zone '{net.zone}' "
                    f"which conflicts with Bridge Domain '{net.bridge_domain}' zone '{bd_zone}'."
                )
            if net.zone is None:
                net.zone = bd_zone

        # 4. ForeignKey Integrity for environment
        if net.environment:
            if net.environment not in environments:
                errors.append(
                    f"ForeignKey Integrity: Environment '{net.environment}' "
                    f"referenced by network '{net.name}' does not exist."
                )

        # 5. ForeignKey Integrity for datacenter
        if net.datacenter:
            if net.datacenter not in datacenters:
                errors.append(
                    f"ForeignKey Integrity: Datacenter '{net.datacenter}' "
                    f"referenced by network '{net.name}' does not exist."
                )

        # 6. ForeignKey Integrity for zone
        if net.zone:
            if net.zone not in zones:
                errors.append(
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

    if errors:
        raise DatabaseValidationError(errors)
    return networks


def is_relational_mode(directory: str) -> bool:
    # Check if 'networks' directory exists under the target path
    if os.path.isdir(os.path.join(directory, "networks")):
        return True
    # Or if the directory name itself contains 'network'
    basename = os.path.basename(os.path.abspath(directory)).lower()
    if "network" in basename and os.path.isdir(directory):
        return True
    return False


def load_yaml_files_from_subdir(directory: str, subdir: str) -> dict:
    result = {}
    path = os.path.join(directory, subdir)
    if not os.path.isdir(path):
        return result
    for file in sorted(os.listdir(path)):
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
                "reserve_internal_until": network.reserve_internal_until,
            }

            if network.context != "default":
                data["context"] = network.context

            inherited_vlan = None
            inherited_bd = None
            inherited_env = None
            inherited_dc = None
            inherited_zone = None
            inherited_metadata = {"timeservers": None, "dns_nameservers": None, "dns_search": None, "default_mtu": None}

            if True:
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

            if True:
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
                        if alloc.hostname:
                            alloc_data["hostname"] = alloc.hostname
                        if alloc.comment:
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
