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

RATE_LIMIT_DELAY = 2  # seconds between API calls to avoid rate limiting

DEFAULT_PREPENDS = {1: 2, 2: 1, 3: 0}  # Adjusted to balance without over-penalizing Tier 1s

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
            return prefixes[0].get("prefix")
    except Exception as e:
        print(f"Error fetching prefix for IP {ip_str}: {e}")
    return None

def classify_tier_by_asn(asn):
    try:
        resp = requests.get(BGP_API_ASN.format(asn=asn), timeout=10)
        time.sleep(RATE_LIMIT_DELAY)
        resp.raise_for_status()
        data = resp.json()
        upstreams = data.get('data', {}).get('ipv4_upstreams', []) + data.get('data', {}).get('ipv6_upstreams', [])
        upstream_asns = [up['asn'] for up in upstreams if 'asn' in up]

        if any(up_asn in TIER1_ASNS for up_asn in upstream_asns):
            return 1  # Direct Tier 1 connection
        elif upstream_asns:
            return 2  # Indirect but not Tier 1
        else:
            return 3  # No upstreams or unknown
    except Exception as e:
        print(f"Error classifying ASN {asn}: {e}")
    return 3

def get_upstream_tiers_by_prefix(prefix):
    try:
        resp = requests.get(BGP_API_PREFIX.format(prefix=prefix), timeout=10)
        time.sleep(RATE_LIMIT_DELAY)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "ok":
            return 3

        asns = data.get("data", {}).get("asns", [])
        for asn_block in asns:
            asn = asn_block.get("asn")
            if not asn:
                continue
            tier = classify_tier_by_asn(asn)
            return tier

    except Exception as e:
        print(f"Error fetching prefix {prefix}: {e}")
    return 3

def get_upstream_tiers_by_asn(asn):
    return classify_tier_by_asn(asn)

def calculate_prepends(tier, custom_prepends):
    return custom_prepends.get(tier, 0)

def update_yaml(file_path, mode="ipv4", custom_prepends=DEFAULT_PREPENDS):
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    with open(file_path, 'r') as f:
        config = yaml.load(f)

    peers = config.get('peers', {})
    changed = False

    source_ip = config.get("source4") if mode == "ipv4" else config.get("source6")
    tier = 3
    if source_ip and not is_private_ip(source_ip):
        prefix = get_prefix_from_ip_api(source_ip)
        if prefix:
            tier = get_upstream_tiers_by_prefix(prefix)
    else:
        for peer_name, peer_conf in peers.items():
            peer_asn = peer_conf.get('asn')
            if peer_asn:
                tier = get_upstream_tiers_by_asn(peer_asn)
                break

    for peer_name, peer_conf in peers.items():
        peer_asn = peer_conf.get('asn')
        if not peer_asn:
            continue

        # Only apply prepend logic if the template is 'upstream'
        if peer_conf.get('template') != 'upstream':
            continue

        prepend_count = calculate_prepends(tier, custom_prepends)

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

def parse_prepends_arg(arg):
    try:
        parts = arg.split(",")
        if len(parts) != 3:
            raise ValueError
        return {1: int(parts[0]), 2: int(parts[1]), 3: int(parts[2])}
    except Exception:
        print("Invalid --prepends format. Use: --prepends 2,1,0")
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: ./update_prepends.py <files_directory> [--ipv4|--ipv6] [--prepends 2,1,0]")
        sys.exit(1)

    mode = "ipv4"
    custom_prepends = DEFAULT_PREPENDS

    if "--ipv6" in sys.argv:
        mode = "ipv6"
    if "--prepends" in sys.argv:
        try:
            idx = sys.argv.index("--prepends") + 1
            custom_prepends = parse_prepends_arg(sys.argv[idx])
        except (IndexError, ValueError):
            print("Error: --prepends flag requires a value like 2,1,0")
            sys.exit(1)

    print("Tier 1 ASNs and Networks included in this script:")
    for asn, name in sorted(TIER1_ASNS.items()):
        print(f" - AS{asn}: {name}")

    files_dir = sys.argv[1]

    for root, dirs, files in os.walk(files_dir):
        for filename in files:
            if filename.endswith('.yml') or filename.endswith('.yaml'):
                file_path = os.path.join(root, filename)
                update_yaml(file_path, mode, custom_prepends)

if __name__ == "__main__":
    main()
