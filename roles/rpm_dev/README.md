# RPM Development Environment Role

This Ansible role sets up a complete RPM development environment for Fedora, AlmaLinux, and Rocky Linux, including the Mock build system for clean, reproducible package builds.

## Features

- **Complete RPM toolchain**: Installs all necessary packages for RPM development
- **Mock build system**: Configures Mock for isolated, clean builds
- **User environment**: Sets up proper user permissions and build directories
- **Custom configurations**: Provides optimized mock and RPM macro configurations
- **Multi-distribution support**: Configured for Fedora 43, AlmaLinux 8/9/10, and Rocky Linux 8/9/10

## Requirements

- Fedora 43, AlmaLinux 8/9/10, or Rocky Linux 8/9/10 system
- Ansible 2.9 or higher
- User with sudo privileges

## Role Variables

### Core Configuration

```yaml
# User configuration
rpm_dev_user:
  name: "{{ ansible_user_id }}"
  groups: ["mock"]

# Package installation control
rpm_dev_install_packages: true
rpm_dev_setup_user: true
rpm_dev_setup_mock: true
rpm_dev_setup_directories: true

# Mock configuration
mock_config:
  enable_network: false        # Security: disable network during builds
  enable_bootstrap: true       # Use bootstrap for faster builds
  cache_topdir: /var/cache/mock
  root_cache_enable: true      # Cache build environments
  cleanup_on_success: true     # Clean up after successful builds

# Build directories
rpm_build:
  build_dir: "{{ ansible_env.HOME }}/rpmbuild"
  setup_macros: true
```

### Mock Targets

Mock targets are automatically selected based on the detected distribution:

```yaml
# Fedora (auto-detected)
mock_targets:
  - fedora-43-x86_64
  - fedora-43-aarch64

# AlmaLinux (stock configs from /etc/mock/)
mock_targets:
  - almalinux-10-x86_64
  - almalinux-10-aarch64

# Rocky Linux (custom configs deployed by role)
mock_targets:
  - rocky-10-x86_64
  - rocky+epel-10-x86_64
```

Override per-host if needed:

```yaml
mock_targets:
  - almalinux-9-x86_64
```

## Installed Packages

The role installs comprehensive RPM development tools:

- **Core tools**: `mock`, `rpm-build`, `rpmdevtools`, `rpmlint`
- **Fedora packaging**: `fedpkg`, `fedora-packager`, `spectool`
- **Development**: `@development-tools`, `git`, `patch`
- **Utilities**: `createrepo_c`, `koji`, `rpm-sign`

## Usage Examples

### Basic Setup

```yaml
- hosts: workstation
  become: yes
  roles:
    - rpm-dev
```

### AlmaLinux Build Server

```yaml
- hosts: almalinux_builders
  become: yes
  vars:
    rpm_dev_user:
      name: "packager"
      groups: ["mock", "wheel"]
    mock_config:
      enable_network: true
      cleanup_on_failure: false
  roles:
    - rpm-dev
```

### Custom Configuration

```yaml
- hosts: workstation
  become: yes
  vars:
    rpm_dev_user:
      name: "packager"
      groups: ["mock", "wheel"]
    mock_config:
      enable_network: true
      cleanup_on_failure: false
  roles:
    - rpm-dev
```

### Tag-based Execution

```bash
# Install packages only
ansible-playbook playbook.yml --tags "packages"

# Set up user and directories only
ansible-playbook playbook.yml --tags "user-setup,directories"

# Configure mock only
ansible-playbook playbook.yml --tags "mock-setup,mock-config"
```

## Directory Structure Created

After running this role, the following structure is created:

```
~/rpmbuild/
├── BUILD/     # Build workspace
├── RPMS/      # Built binary RPMs
├── SOURCES/   # Source tarballs and patches
├── SPECS/     # RPM spec files
└── SRPMS/     # Source RPMs
```

## Mock Usage

After setup, you can build RPMs using mock:

```bash
# Initialize a build environment
mock -r fedora-43-x86_64 --init
mock -r almalinux-10-x86_64 --init

# Build an SRPM
mock -r fedora-43-x86_64 package.src.rpm
mock -r almalinux-10-x86_64 package.src.rpm

# Build using custom configuration
mock -r custom-fedora-43-x86_64 package.src.rpm
mock -r almalinux+epel-10-x86_64 package.src.rpm
```

### AlmaLinux-specific Notes

AlmaLinux ships stock mock configs in `/etc/mock/` for x86_64 and aarch64. No custom templates are needed. For EPEL packages, use the `almalinux+epel` template deployed by this role.

## Security Considerations

- Mock runs with elevated privileges and can execute arbitrary code
- Network access is disabled by default during builds for security
- Only build packages from trusted sources
- Consider using this role in a VM for untrusted package builds

## Integration with Existing Playbooks

This role integrates seamlessly with the existing multi-distribution architecture:

```yaml
# Fedora workstation
- hosts: fedora_workstations
  become: yes
  roles:
    - base
    - rpm-dev
    - tools

# AlmaLinux build server
- hosts: almalinux_builders
  become: yes
  roles:
    - base
    - rpm-dev
    - tools

# Mixed fleet
- hosts: all_builders
  become: yes
  roles:
    - rpm-dev
```

## Troubleshooting

### Permission Issues
If mock commands fail with permission errors:
```bash
# Verify user is in mock group
groups $USER

# If not, re-login or run:
newgrp mock
```

### Cache Issues
To clear mock caches:
```bash
sudo mock --scrub=all
```

### Build Failures
Check mock logs:
```bash
# Fedora
sudo mock -r fedora-43-x86_64 --shell

# AlmaLinux
sudo mock -r almalinux-10-x86_64 --shell

# Examine results
ls /var/lib/mock/*/result/
```

## Dependencies

This role can optionally depend on the `base` role for fundamental development tools:

```yaml
rpm_dev_install_base_deps: true
```

## Testing

Test the role:

```bash
cd tests/
ansible-playbook -i inventory test.yml
```

## License

MIT

## Author

Ansible Automation Framework
