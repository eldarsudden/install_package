# install_package

An Ansible role for managing RPM packages on RHEL-family hosts. Install from enabled repositories, copy an RPM from the Ansible controller, download an RPM over HTTP(S), or remove packages by name.

The role processes package lists internally and checks `ansible_facts['os_family'] == 'RedHat'`; it does not hard-code OS major versions.

## Requirements

- Ansible 2.10 or later on the controller, as declared in [meta/main.yml](meta/main.yml).
- RHEL-family managed hosts with Python and a working DNF/YUM backend that supports the requested package operation.
- SSH access and privilege escalation on the managed hosts.
- Facts gathering enabled.
- Enabled repositories for repository packages and any required RPM dependencies.
- For URL installs, network access from the **managed host** to the artifact URL. For local installs, the RPM must be readable on the **controller**.

## Quick start

Create a playbook directory and install the role under `roles/install_package` so Ansible can find it:

```bash
mkdir -p rpm-deployment/roles
cd rpm-deployment
git clone https://github.com/eldarsudden/install_package.git roles/install_package
cp roles/install_package/deploy.yml deploy.yml
cp roles/install_package/inventory.ini.example inventory.ini
```

Edit `inventory.ini` with your hosts:

```ini
[rhel_servers]
server01.example.com
```

The included [deploy.yml](deploy.yml) enables facts gathering and privilege escalation:

```yaml
---
- name: Manage RPM packages
  hosts: rhel_servers
  become: true
  gather_facts: true
  roles:
    - role: install_package
```

Check playbook syntax, then run it:

```bash
ansible-playbook -i inventory.ini deploy.yml --syntax-check
ansible-playbook -i inventory.ini deploy.yml
```

Add `-u <ssh-user>` to select a remote user and `--ask-become-pass` if sudo requires a password.

With no package overrides, this installs the default repository packages listed below. The expected layout is:

```text
rpm-deployment/
├── deploy.yml
├── inventory.ini
└── roles/
    └── install_package/
        ├── defaults/
        ├── meta/
        └── tasks/
```

## Configuration

Set variables in inventory, `group_vars`, `host_vars`, or playbook role variables. See [defaults/main.yml](defaults/main.yml) for the full defaults.

### Package lists

| Variable | Default | Behavior |
| --- | --- | --- |
| `packages_defaults` | List below | Base package list; can be overridden. |
| `packages` | `"{{ packages_defaults }}"` | List of package names or objects. Set to `null` for single-package mode. |
| `packages_merge_defaults` | `false` | Replace the base list by default; set to the YAML boolean `true` to merge. |

Default repository packages:

```yaml
packages_defaults:
  - bash-completion
  - net-tools
  - bind-utils
  - sysstat
  - strace
  - vim
  - lsof
  - unzip
  - bc
  - tree
  - git
```

List behavior:

- `packages_merge_defaults: false`: process only `packages`. An empty list does nothing.
- `packages_merge_defaults: true`: process base entries whose names do not appear in `packages`, then process `packages` in its original order. An empty list processes only the base list.
- `packages: null`: process one package using the `package_*` variables, regardless of the merge option.

In merge mode, an inventory entry replaces the entire base entry with the same name. Omitted object fields inherit the corresponding `package_*` variables, not fields from the replaced base entry. Duplicate entries within `packages` are still processed individually.

A host-level `packages` list replaces a group-level list according to Ansible variable precedence. The merge option combines the resulting list with `packages_defaults`; it does not combine host and group lists.

### Package settings

Each package object can override these settings using the field in the second column. A string entry such as `curl` is equivalent to `{name: curl}`; omitted fields inherit the role variable.

| Role variable | Object field | Default | Description |
| --- | --- | --- | --- |
| `package_source` | `source` | `repo` | `repo`, `local`, or `url`. |
| `package_name` | `name` | `""` | Required for repository installs and all removals. |
| `package_version` | `version` | `""` | Repository version/release, appended to the name as `name-version`. |
| `package_state` | `state` | `present` | `present`, `latest`, or `absent`. Local and URL installs always use `present`. |
| `package_local_path` | `local_path` | `""` | RPM path on the controller; required for `local` installs. |
| `package_url` | `url` | `""` | Direct HTTP(S) RPM URL; required for `url` installs. |
| `package_url_username` | `url_username` | `""` | HTTP Basic Auth username; supply with the password. |
| `package_url_password` | `url_password` | `""` | HTTP Basic Auth password; supply with the username. |
| `package_tmp_dir` | `tmp_dir` | `/var/tmp/ansible-packages` | Staging directory on the managed host. |
| `package_validate_certs` | `validate_certs` | `true` | Verify TLS certificates for URL downloads. |
| `package_checksum` | `checksum` | `""` | Optional `get_url` checksum, such as `sha256:<digest>`; applies to URL downloads. |

## Examples

### Replace the default packages

Save the following as `inventory.yml`. It installs only the specified packages on every host in `rhel_servers`:

```yaml
---
all:
  children:
    rhel_servers:
      hosts:
        server01.example.com:
      vars:
        packages:
          - curl
          - name: nginx
            version: '1.24.0-1.el9' # Example only; must exist in an enabled repo.
            state: present
          - name: vim-enhanced
            state: latest
```

Run the same playbook with the YAML inventory:

```bash
ansible-playbook -i inventory.yml deploy.yml
```

Alternatively, start with `cp roles/install_package/inventory.yml.example inventory.yml` and adjust the host and packages.

The pinned entry is passed to the package manager as `nginx-1.24.0-1.el9`. Use `present` with a version pin and omit `version` when requesting `latest`.

### Extend the default list

Use these group variables to keep the base packages, add `curl` and `nginx`, and update the base `vim` entry:

```yaml
packages_merge_defaults: true
packages:
  - curl
  - name: nginx
    version: '1.24.0-1.el9' # Example only; must exist in an enabled repo.
    state: present
  - name: vim
    state: latest
```

The base `vim` entry is replaced, so it is processed once.

### Mix repository, local, and URL sources

Use these group variables to install from multiple sources and remove an old package:

```yaml
packages:
  - name: nginx
    source: repo
  - source: local
    local_path: /srv/rpms/myapp-1.0.0.x86_64.rpm
  - source: url
    url: https://nexus.example.com/repository/rpm/agent.rpm
  - name: old-agent
    state: absent
```

Local and URL installs do not require `name`. Removal always requires the installed package name and skips copying or downloading an RPM.

### Manage one package

Set `packages: null` explicitly to use only the single-package variables:

```yaml
packages: null
package_source: repo
package_name: nginx
package_state: present
```

To remove it, set `package_state: absent`.

### Download from an authenticated repository

Use a direct artifact URL, not a Nexus or Artifactory UI page:

```yaml
packages: null
package_source: url
package_url: https://nexus.example.com/repository/rpm/agent.rpm
package_url_username: "{{ vault_rpm_username }}"
package_url_password: "{{ vault_rpm_password }}"
package_validate_certs: true
```

Create an encrypted variables file and define `vault_rpm_username` and `vault_rpm_password` inside it:

```bash
ansible-vault create vault.yml
ansible-playbook -i inventory.yml deploy.yml -e @vault.yml --ask-vault-pass
```

Leave both credentials empty for anonymous access, or supply both for HTTP Basic Auth. Supplying only one fails validation. The download task uses `no_log: true`.

## Operational notes

- With `--check`, URL package settings are validated and staging directory creation is previewed, but RPM downloads and URL package installation are skipped with an explanatory message. This does not verify URL access, RPM contents, or dependencies. Run without `--check` to download and install the RPM.
- Package operations use `ansible.builtin.package`; RPM path support and dependency resolution depend on the selected DNF/YUM backend.
- `latest` applies to repository installs. Local and URL RPM installs always use `present`; `version` is used only for repository installs.
- Local RPMs are staged under their original filename. URL RPMs are staged as `package.rpm` in the selected `tmp_dir`; sequential URL entries using the same directory reuse that path.
- Staged RPM files remain on the managed host after installation.
- TLS verification is enabled by default. Keep it enabled for HTTPS downloads.
- The role does not configure package repositories, perform a separate RPM GPG signature verification step, or manage services.

## Tests

With Ansible installed, run:

```bash
python3 -m unittest discover -s tests -v
```

The tests use a local HTTP server to verify downloads and check-mode behavior with missing and existing staging directories. They do not install RPM packages or require a RHEL host.
