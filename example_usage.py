from net_mgmt import load_all_networks


def main():
    networks = load_all_networks("networks")

    print("Found networks:")
    for net in networks:
        print(f"- {net.name}: {net.cidr} ({net.description})")
        if net.reservations:
            print("  Reservations:")
            for res in net.reservations:
                print(f"    - {res.cidr}: {res.comment}")


if __name__ == "__main__":
    main()
