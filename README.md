# install_package

Ansible role for RPM deployment to RHEL-family distributions, without hard-coded OS major versions. Requires Ansible 2.10+, facts gathering and privilege escalation. Uses `ansible.builtin.package`; installing RPM file paths depends on the selected package manager (DNF/YUM).

## Variables

| Variable | Default | Description |
|---|---|---|
| `packages` | `null` | List of names or package objects; the role loops internally. `null` uses the single-package variables below; `[]` does nothing |
| `package_source` | `repo` | `repo`, `local`, or `url` |
| `package_name` | `""` | Package name (required for repo/removal) |
| `package_version` | `""` | Optional repository package version/release |
| `package_state` | `present` | `present`, `latest`, or `absent` |
| `package_local_path` | `""` | RPM on Ansible controller |
| `package_url` | `""` | Direct HTTP(S) URL to RPM |
| `package_url_username` | `""` | Optional HTTP Basic username |
| `package_url_password` | `""` | Optional password; requires username |
| `package_tmp_dir` | `/var/tmp/ansible-packages` | Remote RPM staging directory |
| `package_validate_certs` | `true` | TLS certificate verification |
| `package_checksum` | `""` | Optional get_url checksum, e.g. `sha256:...` |

Package objects use `name`, `version`, `state`, `source`, `local_path`, `url`, `url_username`, `url_password`, `tmp_dir`, `validate_certs`, and `checksum`. Omitted fields inherit the corresponding `package_*` variable. A string entry is equivalent to `{name: <string>}`.

## Usage

All examples use `hosts: rhel_servers`, `become: true`, and facts gathering.

### Repository

```yaml
- hosts: rhel_servers
  become: true
  roles:
    - role: install_package
      vars:
        package_source: repo
        package_name: nginx
        package_state: present
```

### Repository: pinned version

```yaml
- hosts: rhel_servers
  become: true
  roles:
    - role: install_package
      vars:
        package_source: repo
        package_name: nginx
        package_version: '1.24.0-1.el9' # example only; must exist in repo
```

### Repository: latest version

```yaml
- hosts: rhel_servers
  become: true
  roles:
    - role: install_package
      vars:
        package_name: nginx
        package_state: latest
```

### Local RPM on controller

```yaml
- hosts: rhel_servers
  become: true
  roles:
    - role: install_package
      vars:
        package_source: local
        package_local_path: files/myapp-1.0.0.x86_64.rpm
```

### Public Nexus / direct URL (no password)

```yaml
- hosts: rhel_servers
  become: true
  roles:
    - role: install_package
      vars:
        package_source: url
        package_url: https://nexus.example.com/repository/rpm/myapp.rpm
```

### Private Nexus with Basic authentication

```yaml
- hosts: rhel_servers
  become: true
  roles:
    - role: install_package
      vars:
        package_source: url
        package_url: https://nexus.example.com/repository/rpm/myapp.rpm
        package_url_username: "{{ nexus_user }}"
        package_url_password: "{{ nexus_password }}"
```

Store credentials in Ansible Vault or a secrets manager. A username with an empty password is permitted; a password without a username is rejected.

### Artifactory

```yaml
- hosts: rhel_servers
  become: true
  roles:
    - role: install_package
      vars:
        package_source: url
        package_url: https://artifactory.example.com/artifactory/rpm-local/myapp.rpm
```

### URL with SHA256 verification

```yaml
- hosts: rhel_servers
  become: true
  roles:
    - role: install_package
      vars:
        package_source: url
        package_url: https://nexus.example.com/repository/rpm/myapp.rpm
        package_checksum: 'sha256:REPLACE_WITH_ACTUAL_SHA256'
```

### Remove package (all sources)

```yaml
- hosts: rhel_servers
  become: true
  roles:
    - role: install_package
      vars:
        package_name: myapp
        package_state: absent
```

### YAML inventory: package list for a group

Define `packages` in `inventory.yml` to install the same repository packages on every host in the group. The role processes each entry internally.

```yaml
all:
  children:
    rhel_servers:
      hosts:
        server01.example.com:
        server02.example.com:
      vars:
        package_source: repo
        packages:
          - nginx
          - curl
          - vim-enhanced
        package_state: present
```

The existing `deploy.yml` calls the role once and takes its configuration from inventory:

```yaml
- name: Install packages from inventory
  hosts: rhel_servers
  become: true
  gather_facts: true
  roles:
    - role: install_package
```

```bash
ansible-playbook -i inventory.yml deploy.yml
```

### YAML inventory: individual package versions and states

For separate settings per package, define a list of objects in `inventory.yml`. Use the same `deploy.yml`; the loop remains inside the role. Group variables provide the default list; a host-level list replaces it for that host (lists are not combined).

```yaml
all:
  children:
    rhel_servers:
      hosts:
        server01.example.com:
        server02.example.com:
          packages:
            - name: curl
              state: latest
            - name: httpd
              state: absent
      vars:
        packages:
          - name: nginx
            version: '1.24.0-1.el9' # example only; must exist in repo
          - name: curl
            state: latest
          - name: vim-enhanced
```

### YAML inventory: mixed package sources

Repository packages, local RPMs, and URL downloads can share one list. Removal requires `name`, regardless of source.

```yaml
all:
  children:
    rhel_servers:
      hosts:
        server01.example.com:
      vars:
        packages:
          - name: nginx
            source: repo
          - source: local
            local_path: files/myapp-1.0.0.x86_64.rpm
          - source: url
            url: https://nexus.example.com/repository/rpm/agent.rpm
          - name: old-agent
            state: absent
```

```bash
ansible-playbook -i inventory.yml deploy.yml
```

## Run

```bash
ansible-playbook -i inventory.ini deploy.yml
```

Alternatively, copy `inventory.yml.example` to `inventory.yml`, adjust the hosts and packages, and run:

```bash
ansible-playbook -i inventory.yml deploy.yml
```

## Notes

- The URL must point directly to an RPM artifact, not a Nexus/Artifactory UI page.
- `latest` applies to repository installs; RPM file installs use `present`.
- The role does not configure repositories, verify RPM GPG signatures separately, remove staged RPM files, or manage services.
- TLS verification is enabled by default. Do not disable it except in controlled environments.
- `get_url` uses `no_log: true` to avoid exposing credentials in logs.

### Nexus authentication validation

For `package_source: url`, either leave both `package_url_username` and `package_url_password` empty (anonymous access), or supply both values (HTTP Basic Auth). Supplying only one value fails validation. Credentials should be provided through Ansible Vault or a secret manager.
