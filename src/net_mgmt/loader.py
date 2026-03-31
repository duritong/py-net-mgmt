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


def load_all_networks(directory: str) -> List[Network]:
    networks = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".yaml") or file.endswith(".yml"):
                networks.append(load_network_from_file(os.path.join(root, file)))
    return networks


def save_network_to_file(network: Network):
    """Save network configuration back to its YAML file."""
    if not network.file_path:
        raise ValueError("Network has no file path associated with it.")

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

            if network.vlan is not None:
                data["vlan"] = network.vlan
            if network.bridge_domain:
                data["bridge_domain"] = network.bridge_domain
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
            if network.static_routes:
                data["static_routes"] = [{"cidr": sr.cidr, "gateway": sr.gateway} for sr in network.static_routes]
            if network.zone:
                data["zone"] = network.zone
            if network.datacenter:
                data["datacenter"] = network.datacenter
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
