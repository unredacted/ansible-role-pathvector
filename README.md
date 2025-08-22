# ansible-role-pathvector

An Ansible role to install and configure [Pathvector](https://pathvector.io/) & Bird2 with automatic UniFi detection and support.

## Features

- Automatic detection of UniFi vs standard Debian systems
- Persistent UniFi on-boot scripts that survive firmware updates
- Standard APT installation for Debian/Ubuntu systems
- BGP AS-path prepend optimization script
- Support for mixed infrastructure (UniFi + Debian in same playbook)

## Requirements

- **Supported Systems**:
  - Debian 11/12, Ubuntu 20.04/22.04
  - UniFi devices with `/data/on_boot.d/` support
- **Ansible**: 2.9+
- **Python**: 3.6+ (with `requests`, `ipaddress`, `ruamel.yaml` for prepend script)

## Installation

```bash
ansible-galaxy install git+https://github.com/unredacted/ansible-role-pathvector.git
```

## Quick Start

### Basic Usage
```yaml
---
- hosts: routers
  become: yes
  roles:
    - ansible-role-pathvector
```

The role automatically detects if it's running on a UniFi system or standard Debian/Ubuntu.

### Configuration Files

Place your Pathvector configuration files in your playbook's `files/` directory:

```
playbook/
└── files/
    ├── router1.yml
    ├── router2.yml
    └── unifi-gateway.yml
```

Files should be named after the inventory hostname (e.g., `router1.yml` for host `router1`).

### Example Configuration

```yaml
# files/router1.yml
asn: 65001
router-id: 192.168.1.1

source4: 203.0.113.1
source6: 2001:db8::1

prefixes:
  - 203.0.113.0/24
  - 2001:db8::/32

rtr-server: rtr.rpki.cloudflare.com:8282

templates:
  upstream:
    interpret-communities: true
    filter-max-prefix: true
    filter-rpki: true
    filter-bogon-routes: true
    filter-bogon-asns: true

peers:
  cogent:
    asn: 174
    template: upstream
    neighbors:
      - 38.140.0.1
      - 2001:550:1::1
```

## Role Variables

### Common Variables
```yaml
pathvector_config_path: "/etc/pathvector.yml"  # Config destination
pathvector_debug: false                        # Enable debug output
pathvector_run_script: false                   # Run prepend optimization
pathvector_script_flags: ""                    # Prepend script flags
```

### UniFi-Specific Variables
```yaml
pathvector_unifi_script_name: "1-unifi-pathvector-setup.sh"  # On-boot script name
pathvector_unifi_run_immediately: false                      # Install immediately
pathvector_unifi_autostart_services: false                   # Auto-start services
```

### Repository Configuration
```yaml
pathvector_pgp_key_url: "https://repo.pathvector.io/pgp.asc"
pathvector_repo_url: "https://repo.pathvector.io/apt/"
pathvector_repo_dist: "stable"
pathvector_repo_component: "main"
```

## How It Works

### For UniFi Systems
1. Deploys a persistent on-boot script to `/data/on_boot.d/`
2. Copies your configuration to `/data/on_boot.d/pathvector.yml`
3. On boot, the script:
   - Installs bird2 and pathvector (if needed)
   - Copies config from persistent storage to `/etc/`
   - Runs `pathvector generate`
   - Logs to `/var/log/unifi-pathvector-setup.log`

### For Debian/Ubuntu Systems
1. Adds Pathvector repository
2. Installs bird2 and pathvector packages
3. Deploys configuration to `/etc/pathvector.yml`
4. Starts and enables bird service

## Advanced Usage

### Run Installation Immediately on UniFi
```yaml
- hosts: unifi_devices
  become: yes
  roles:
    - ansible-role-pathvector
  vars:
    pathvector_unifi_run_immediately: true
    pathvector_unifi_autostart_services: true
```

### Enable Prepend Optimization
```yaml
- hosts: routers
  become: yes
  roles:
    - ansible-role-pathvector
  vars:
    pathvector_run_script: true
    pathvector_script_flags: "--prepends 2,1,0 --ignore router1.yml"
```

### Mixed Infrastructure
```yaml
# Works automatically with both UniFi and Debian hosts
- hosts: all_routers
  become: yes
  roles:
    - ansible-role-pathvector
```

## Troubleshooting

### Enable Debug Mode
```yaml
pathvector_debug: true
```

## License

GPL-3.0

## Author

Zach - [Unredacted](https://unredacted.org/)
