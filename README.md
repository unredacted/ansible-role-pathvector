ansible-role-pathvector
=========

An Ansible role to install and configure [Pathvector](https://pathvector.io/) & Bird.

Requirements
------------

Currently only tested on Debian 12, so use with caution on other Debian versions.

Role Variables
--------------

There are not many variables for this role at the moment. The intended use for this role is to specify your own Pathvector configuration files in the files/ directory where your playbook exists, so that they can be transferred to the host & deployed with Pathvector. It's possible in the future this role will templatize the Pathvector configuration so that it can all be defined in variables.

Review the [Pathvector docs](https://pathvector.io/docs/about) to understand what else you can set.

Examples vars:

```
vars:
    pathvector_repo: "deb [signed-by=/usr/share/keyrings/pathvector.asc] https://repo.pathvector.io/apt/ stable main"
    pathvector_config_path: "/etc/pathvector.yml"
```

Example file (where router1 is the host): `files/upstream_name/router1.yml`

```
asn: AS_NUMBER_HERE
router-id: IP_HERE

source4: IPV4_HERE
source6: IPV6_HERE

prefixes:
  - PREFIXES_HERE

rtr-server: rtr.rpki.cloudflare.com:8282

templates:
  upstream:
    interpret-communities: true
    filter-max-prefix: true
    filter-rpki: true
    filter-bogon-routes: true
    filter-bogon-asns: true

peers:
  PEER_NAME_HERE:
    asn: AS_NUMBER_HERE
    template: upstream
    neighbors:
      - IP_HERE
      - IP_HERE
```

Dependencies
------------

None.

Example Playbook
----------------

```
---

- hosts: '{{ target }}'
  become: yes
  roles:
    - ansible-role-pathvector
```

License
-------

GPL-3

Author Information
------------------

Zach - [Unredacted](https://unredacted.org/)