import fcntl
import io
import ipaddress
import os
from typing import List

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

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


def get_yaml_handler() -> YAML:
    yaml_rt = YAML(typ="rt")
    yaml_rt.preserve_quotes = True
    yaml_rt.indent(mapping=2, sequence=4, offset=2)
    yaml_rt.width = 120
    return yaml_rt


def get_item_start_ip(item):
    val = item.get("cidr") or item.get("ip")
    if not val:
        comment_val = item.get("comment", "")
        return (ipaddress.ip_address("255.255.255.255"), comment_val)
    val_str = str(val).split("-")[0].strip()
    try:
        return (ipaddress.ip_address(val_str), "")
    except ValueError:
        try:
            return (ipaddress.ip_network(val_str, strict=False).network_address, "")
        except ValueError:
            return (ipaddress.ip_address("255.255.255.255"), val_str)


def format_yaml_node(node):
    if isinstance(node, (CommentedMap, dict)):
        cmap_keys = list(node.keys())
        sorted_keys = []

        primary_order = [
            "id",
            "cidr",
            "ip",
            "hostname",
            "description",
            "comment",
            "epg",
            "environment",
            "datacenter",
            "zone",
            "bridge_domain",
        ]
        for field in primary_order:
            if field in cmap_keys:
                sorted_keys.append(field)

        last_keys = []
        for last_key in ["reservations", "allocations"]:
            if last_key in cmap_keys:
                last_keys.append(last_key)

        other = []
        for k in cmap_keys:
            if k not in sorted_keys and k not in last_keys:
                other.append(k)
        other.sort()

        all_sorted_keys = sorted_keys + other + last_keys

        for k in all_sorted_keys:
            node[k] = format_yaml_node(node[k])

        new_map = CommentedMap()
        if hasattr(node, "ca") and node.ca:
            new_map.ca.comment = node.ca.comment
        for k in all_sorted_keys:
            new_map[k] = node[k]
            if hasattr(node, "ca") and k in node.ca.items:
                new_map.ca.items[k] = node.ca.items[k]
        return new_map

    elif isinstance(node, (CommentedSeq, list)):
        if len(node) > 0 and isinstance(node[0], (CommentedMap, dict)):
            is_reservations = "cidr" in node[0] and "id" in node[0]
            is_allocations = "ip" in node[0] or "cidr" in node[0]
            if is_reservations or is_allocations:
                node = sorted(node, key=get_item_start_ip)

        new_seq = CommentedSeq()
        if hasattr(node, "ca") and node.ca:
            new_seq.ca.comment = node.ca.comment
        for i, item in enumerate(node):
            formatted_item = format_yaml_node(item)
            new_seq.append(formatted_item)
            if hasattr(node, "ca") and i in node.ca.items:
                new_seq.ca.items[i] = node.ca.items[i]
        return new_seq

    return node


def save_network_to_file(network: Network):
    """Save network configuration back to its YAML file using standard formatting."""
    if not network.file_path:
        raise ValueError("Network has no file path associated with it.")

    db_dir = os.path.dirname(os.path.dirname(network.file_path))

    with open(network.file_path, "a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            lock_file.seek(0)
            original_content = lock_file.read()

            yaml_rt = get_yaml_handler()
            data = None
            if original_content.strip():
                try:
                    data = yaml_rt.load(original_content)
                except Exception:
                    data = None

            if data is None or not isinstance(data, (CommentedMap, dict)):
                data = CommentedMap()

            data["cidr"] = str(network.cidr)
            if network.routable is not None:
                data["routable"] = network.routable
            elif "routable" in data:
                del data["routable"]

            if network.reserve_gateway is not None:
                data["reserve_gateway"] = network.reserve_gateway
            elif "reserve_gateway" in data:
                del data["reserve_gateway"]

            if network.reserve_internal is not None:
                data["reserve_internal"] = network.reserve_internal
            elif "reserve_internal" in data:
                del data["reserve_internal"]

            if network.reserve_internal_until is not None:
                data["reserve_internal_until"] = network.reserve_internal_until
            elif "reserve_internal_until" in data:
                del data["reserve_internal_until"]

            if network.context and network.context != "default":
                data["context"] = network.context
            elif "context" in data:
                del data["context"]

            inherited_vlan = None
            inherited_bd = None
            inherited_env = None
            inherited_dc = None
            inherited_zone = None
            inherited_metadata = {
                "timeservers": None,
                "dns_nameservers": None,
                "dns_search": None,
                "default_mtu": None,
            }

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

            if network.epg:
                data["epg"] = network.epg
            elif "epg" in data:
                del data["epg"]

            if network.vlan is not None and (network.epg is None or network.vlan != inherited_vlan):
                data["vlan"] = network.vlan
            elif "vlan" in data:
                del data["vlan"]

            if network.bridge_domain and (network.epg is None or network.bridge_domain != inherited_bd):
                data["bridge_domain"] = network.bridge_domain
            elif "bridge_domain" in data:
                del data["bridge_domain"]

            if network.environment and (network.epg is None or network.environment != inherited_env):
                data["environment"] = network.environment
            elif "environment" in data:
                del data["environment"]

            if network.datacenter and (network.epg is None or network.datacenter != inherited_dc):
                data["datacenter"] = network.datacenter
            elif "datacenter" in data:
                del data["datacenter"]

            if network.zone and (network.epg is None or network.zone != inherited_zone):
                data["zone"] = network.zone
            elif "zone" in data:
                del data["zone"]

            # For metadata: write only if different from inherited (and not None)
            for field_name in ["timeservers", "dns_nameservers", "dns_search", "default_mtu"]:
                val = getattr(network, field_name, None)
                if val is not None and val != inherited_metadata[field_name]:
                    data[field_name] = val
                elif field_name in data:
                    del data[field_name]

            if network.static_routes:
                data["static_routes"] = [{"cidr": sr.cidr, "gateway": sr.gateway} for sr in network.static_routes]
            elif "static_routes" in data:
                del data["static_routes"]

            if network.description:
                data["description"] = network.description
            elif "description" in data:
                del data["description"]

            if network.reservations:
                existing_res_maps = {}
                if "reservations" in data and isinstance(data["reservations"], (CommentedSeq, list)):
                    for item in data["reservations"]:
                        if isinstance(item, (CommentedMap, dict)) and "id" in item:
                            existing_res_maps[str(item["id"])] = item

                res_list = CommentedSeq()
                for res in network.reservations:
                    res_id_str = str(res.id)
                    if res_id_str in existing_res_maps:
                        res_data = existing_res_maps[res_id_str]
                    else:
                        res_data = CommentedMap()

                    res_data["id"] = res.id
                    res_data["cidr"] = res.cidr
                    if res.comment:
                        res_data["comment"] = res.comment
                    elif "comment" in res_data:
                        del res_data["comment"]

                    if res.allocatable:
                        res_data["allocatable"] = True
                    elif "allocatable" in res_data:
                        del res_data["allocatable"]

                    res_list.append(res_data)
                data["reservations"] = res_list
            elif "reservations" in data:
                del data["reservations"]

            if network.allocations:
                existing_alloc_maps = {}
                if "allocations" in data and isinstance(data["allocations"], (CommentedSeq, list)):
                    for item in data["allocations"]:
                        if isinstance(item, (CommentedMap, dict)):
                            k = item.get("ip") or item.get("cidr")
                            if k:
                                existing_alloc_maps[str(k)] = item

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
                alloc_list = CommentedSeq()
                for alloc in sorted_allocs:
                    alloc_key = str(alloc.ip) if alloc.ip else str(alloc.cidr)
                    if alloc_key in existing_alloc_maps:
                        alloc_data = existing_alloc_maps[alloc_key]
                    else:
                        alloc_data = CommentedMap()

                    if alloc.ip:
                        alloc_data["ip"] = str(alloc.ip)
                        if "cidr" in alloc_data:
                            del alloc_data["cidr"]
                    elif alloc.cidr:
                        alloc_data["cidr"] = alloc.cidr
                        if "ip" in alloc_data:
                            del alloc_data["ip"]

                    if alloc.hostname:
                        alloc_data["hostname"] = alloc.hostname
                    elif "hostname" in alloc_data:
                        del alloc_data["hostname"]

                    if alloc.comment:
                        alloc_data["comment"] = alloc.comment
                    elif "comment" in alloc_data:
                        del alloc_data["comment"]

                    alloc_list.append(alloc_data)
                data["allocations"] = alloc_list
            elif "allocations" in data:
                del data["allocations"]

            formatted_data = format_yaml_node(data)

            buf = io.StringIO()
            yaml_rt.dump(formatted_data, buf)
            content_after = buf.getvalue()

            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(content_after)

        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
