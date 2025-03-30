#!/usr/bin/env python3
import sys
import os
import requests
import time
import ipaddress
from ruamel.yaml import YAML

# Tier-1 networks explicitly included:
TIER1_ASNS = {
    174: "Cogent",
    1299: "Telia",
    2914: "NTT",
    3257: "GTT",
    3320: "DTAG",
    3356: "Lumen",
    5511: "Orange",
    6453: "TATA",
    6461: "Zayo",
    6762: "Sparkle",
    6830: "Liberty Global",
    701: "Verizon",
    7018: "AT&T",
    12956: "Telefonica",
    3491: "PCCW",
    6939: "HE (IPv6 Only)",
}

BGP_API_PREFIX = "https://api.bgpview.io/prefix/{prefix}"
BGP_API_ASN = "https://api.bgpview.io/asn/{asn}/upstreams"
BGP_API_IP = "https://api.bgpview.io/ip/{ip}"

RATE_LIMIT_DELAY = 2

PREPENDS_BY_TIER = {
    1: 3,  # Our network has direct Tier 1 connection
    2: 2,  # Our upstream has direct Tier 1 connection
    3: 1   # Our upstream has no Tier 1 connection
}

def is_private_ip(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private
    except ValueError:
        return True

def get_prefix_from_ip_api(ip_str):
    try:
        resp = requests.get(BGP_API_IP.format(ip=ip_str), timeout=10)
        time.sleep(RATE_LIMIT_DELAY)
        resp.raise_for_status()
        data = resp.json()
        prefixes = data.get("data", {}).get("prefixes", [])
        if prefixes:
            return prefixes[0].get("prefix"), prefixes[0].get("asn", {}).get("asn")
    except Exception as e:
        print(f"Error fetching prefix for IP {ip_str}: {e}")
    return None, None

def get_direct_upstreams_from_prefix(prefix):
    try:
        resp = requests.get(BGP_API_PREFIX.format(prefix=prefix), timeout=10)
        time.sleep(RATE_LIMIT_DELAY)
        resp.raise_for_status()
        data = resp.json()
        asns = data.get("data", {}).get("asns", [])
        if not asns:
            return []
        return [upstream.get("asn") for upstream in asns[0].get("prefix_upstreams", []) if "asn" in upstream]
    except Exception as e:
        print(f"Error fetching upstreams from prefix {prefix}: {e}")
    return []

def determine_tier(my_asn, prefix, prefix_asn):
    if my_asn and int(my_asn) in TIER1_ASNS:
        return 1
    if prefix_asn and int(prefix_asn) in TIER1_ASNS:
        return 1
    upstreams = get_direct_upstreams_from_prefix(prefix)
    if any(int(up) in TIER1_ASNS for up in upstreams):
        return 2
    return 3

def update_yaml(file_path, mode="ipv4", ignore_files=[], limit_hosts=[]):
    if os.path.basename(file_path) in ignore_files:
        print(f"Skipping ignored file: {file_path}")
        return

    filename_host = os.path.basename(file_path).rsplit('.', 1)[0]
    if limit_hosts and filename_host not in limit_hosts:
        return

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    with open(file_path, 'r') as f:
        config = yaml.load(f)

    peers = config.get('peers', {})
    changed = False
    my_asn = config.get("asn")

    source_ip = config.get("source4") if mode == "ipv4" else config.get("source6")
    tier = 3

    if source_ip and not is_private_ip(source_ip):
        prefix, prefix_asn = get_prefix_from_ip_api(source_ip)
        if prefix and prefix_asn:
            tier = determine_tier(my_asn, prefix, prefix_asn)

    prepend_count = PREPENDS_BY_TIER.get(tier, 1)

    for peer_name, peer_conf in peers.items():
        peer_asn = peer_conf.get('asn')
        if not peer_asn or peer_conf.get('template') != 'upstream':
            continue

        if 'prepends' in peer_conf:
            if peer_conf['prepends'] != prepend_count:
                peer_conf['prepends'] = prepend_count
                changed = True
        else:
            new_peer_conf = {}
            for key, value in peer_conf.items():
                new_peer_conf[key] = value
                if key == 'template':
                    new_peer_conf['prepends'] = prepend_count
            peer_conf.clear()
            peer_conf.update(new_peer_conf)
            changed = True

        print(f"Peer {peer_name} (AS{peer_asn}) set prepend to {prepend_count}")

    if changed:
        with open(file_path, 'w') as f:
            yaml.dump(config, f)
        print(f"Updated file: {file_path}")
    else:
        print(f"No changes required for {file_path}")

def parse_arg_list(arg):
    return [x.strip() for x in arg.split(",") if x.strip()]

def main():
    if len(sys.argv) < 2:
        print("Usage: ./update_prepends.py <files_directory> [--ipv4|--ipv6] [--ignore file1.yml,file2.yml] [--hostnames host1,host2]")
        sys.exit(1)

    mode = "ipv4"
    ignore_files = []
    limit_hosts = []

    if "--ipv6" in sys.argv:
        mode = "ipv6"
    if "--ignore" in sys.argv:
        try:
            idx = sys.argv.index("--ignore") + 1
            ignore_files = parse_arg_list(sys.argv[idx])
        except IndexError:
            print("Error: --ignore flag requires a comma-separated list of filenames")
            sys.exit(1)
    if "--hostnames" in sys.argv:
        try:
            idx = sys.argv.index("--hostnames") + 1
            limit_hosts = parse_arg_list(sys.argv[idx])
        except IndexError:
            print("Error: --hostnames flag requires a comma-separated list")
            sys.exit(1)

    print("Tier 1 ASNs and Networks included in this script:")
    for asn, name in sorted(TIER1_ASNS.items()):
        print(f" - AS{asn}: {name}")

    files_dir = sys.argv[1]

    for root, dirs, files in os.walk(files_dir):
        for filename in files:
            if filename.endswith('.yml') or filename.endswith('.yaml'):
                file_path = os.path.join(root, filename)
                update_yaml(file_path, mode, ignore_files, limit_hosts)

if __name__ == "__main__":
    main()
