#!/usr/bin/env ruby
# frozen_string_literal: true

ENV['VAGRANT_DEFAULT_PROVIDER'] = 'libvirt'

# Configuration variables
ALMALINUX_HOSTNAME = 'almalinux-test.syncopated.dev'
FEDORA_HOSTNAME = 'fedora-workstation.syncopated.dev'
FEDORA_BOX = ENV.fetch('FEDORA_BOX', 'fedora/41-cloud-base')
ALMALINUX_BOX = ENV.fetch('ALMALINUX_BOX', 'almalinux/10')

VAGRANT_USER = ENV.fetch('VAGRANT_USER', ENV.fetch('USER', 'vagrant'))

# rubocop:disable Metrics/BlockLength
Vagrant.configure('2') do |config|
  # Global SSH configuration
  config.ssh.insert_key = false
  config.ssh.forward_agent = true

  # Rocky Linux 9 VM for testing
  config.vm.define 'almalinux', primary: true do |almalinux|
    almalinux.vm.box = ALMALINUX_BOX
    almalinux.vm.hostname = ALMALINUX_HOSTNAME

    almalinux.vm.network :private_network,
                         ip: '192.168.122.10',
                         libvirt__network_name: 'default'

    almalinux.vm.provider :libvirt do |libvirt|
      libvirt.memory = 8192
      libvirt.uri = 'qemu:///system'
      libvirt.cpus = 8
      libvirt.nested = true
      libvirt.disk_bus = 'virtio'
      libvirt.cpu_mode = 'host-passthrough'
      libvirt.nic_model_type = 'virtio'
      libvirt.disk_driver cache: 'writeback'
      libvirt.machine_virtual_size = 50
      libvirt.graphics_type = 'spice'
      libvirt.video_type = 'qxl'
    end

    # Sync the entire project for testing
    almalinux.vm.synced_folder '.', '/vagrant',
                               type: 'rsync',
                               rsync__exclude: ['.git/', '*.swp', '.venv/', '.vagrant/']

    # Copy SSH key for testing
    if File.exist?(File.expand_path('~/.ssh/id_ed25519.pub'))
      almalinux.vm.provision 'file',
                             source: '~/.ssh/id_ed25519.pub',
                             destination: '/tmp/id_ed25519.pub'
    end

    # Bootstrap system for testing
    almalinux.vm.provision 'shell', inline: <<-SHELL
      # Update system
      dnf config-manager --set-enabled crb
      # Install required packages
      dnf install -y --setopt=timeout=5 --setopt=retries=2 epel-release
      dnf install -y --setopt=timeout=5 --setopt=retries=2 python3 python3-pip ansible-core git curl make zsh
      dnf install -y --setopt=timeout=5 --setopt=retries=2 ansible-collection-ansible-posix ansible-collection-ansible-utils

      dnf clean all && dnf update -y --setopt=timeout=5 --setopt=retries=2

      # Setup SSH key
      mkdir -p /home/vagrant/.ssh
      chmod 700 /home/vagrant/.ssh
      grep -qF "$(cat /tmp/id_ed25519.pub)" /home/vagrant/.ssh/authorized_keys 2>/dev/null || cat /tmp/id_ed25519.pub >> /home/vagrant/.ssh/authorized_keys
      chmod 600 /home/vagrant/.ssh/authorized_keys
      chown -R vagrant:vagrant /home/vagrant/.ssh

      # Create test user that matches inventory
      useradd -m -s /usr/bin/zsh #{VAGRANT_USER} || true
      usermod -aG wheel #{VAGRANT_USER}
      mkdir -p /home/#{VAGRANT_USER}/.ssh
      chmod 700 /home/#{VAGRANT_USER}/.ssh
      grep -qF "$(cat /tmp/id_ed25519.pub)" /home/#{VAGRANT_USER}/.ssh/authorized_keys 2>/dev/null || cat /tmp/id_ed25519.pub >> /home/#{VAGRANT_USER}/.ssh/authorized_keys
      chmod 600 /home/#{VAGRANT_USER}/.ssh/authorized_keys
      chown -R #{VAGRANT_USER}:#{VAGRANT_USER} /home/#{VAGRANT_USER}/.ssh
      echo "#{VAGRANT_USER} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/99-user
      chmod 0440 /etc/sudoers.d/99-user
    SHELL

    # Run Ansible playbook for testing
    almalinux.vm.provision 'ansible' do |ansible|
      ansible.playbook = 'playbooks/workstation.yml'
      ansible.groups = {
        'workstations' => ['almalinux']
      }
      ansible.extra_vars = {
        ansible_python_interpreter: '/usr/bin/python3',
        ansible_user: VAGRANT_USER,
        user: { name: VAGRANT_USER, group: VAGRANT_USER, home: "/home/#{VAGRANT_USER}", shell: '/usr/bin/zsh' },
        # Override variables for testing
        use_containers: false,
        use_kvm: false
      }
      # ansible.tags = ENV['ANSIBLE_TAGS'] || 'cargo'
      ansible.verbose = ENV['ANSIBLE_VERBOSE'] == 'true'
      # ansible.skip_tags = 'libvirt,containerd'
      ansible.raw_arguments = ['--check'] if ENV['ANSIBLE_CHECK']
    end
  end

  # Fedora Workstation VM for testing
  config.vm.define 'fedora', autostart: false do |fedora|
    fedora.vm.box = FEDORA_BOX
    fedora.vm.hostname = FEDORA_HOSTNAME

    fedora.vm.network :private_network,
                      ip: '192.168.122.20',
                      libvirt__network_name: 'default'

    fedora.vm.provider :libvirt do |libvirt|
      libvirt.uri = 'qemu:///system'
      libvirt.memory = 8192
      libvirt.cpus = 8
      libvirt.nested = true
      libvirt.disk_bus = 'virtio'
      libvirt.cpu_mode = 'host-passthrough'
      libvirt.nic_model_type = 'virtio'
      libvirt.disk_driver cache: 'writeback'
      libvirt.machine_virtual_size = 50
      libvirt.graphics_type = 'spice'
      libvirt.video_type = 'qxl'
    end

    # Sync the entire project for testing
    fedora.vm.synced_folder '.', '/vagrant',
                            type: 'rsync',
                            rsync__exclude: ['.git/', '*.swp', '.venv/', '.vagrant/']

    # Copy SSH key for testing
    if File.exist?(File.expand_path('~/.ssh/id_ed25519.pub'))
      fedora.vm.provision 'file',
                          source: '~/.ssh/id_ed25519.pub',
                          destination: '/tmp/id_ed25519.pub'
    end

    # Bootstrap system for testing
    fedora.vm.provision 'shell', inline: <<-SHELL
      # Automatically expand root partition to fill allocated virtual disk
      dnf install -y cloud-utils-growpart 2>/dev/null || true
      growpart /dev/vda 4 2>/dev/null || true
      resize2fs /dev/vda4 2>/dev/null || true

      # Update dnf and install minimal prerequisites
      dnf install -y --setopt=timeout=10 --setopt=retries=3 \
        git \
        ansible-core \
        ansible-collection-ansible-posix \
        ansible-collection-ansible-utils \
        ansible-collection-community-general \
        python3-rich \
        python3-dnf \
        python3-pip \
        zsh \
        curl

      # Create test user matching inventory
      id -u #{VAGRANT_USER} &>/dev/null || useradd -m -s /usr/bin/zsh #{VAGRANT_USER}
      usermod -aG wheel #{VAGRANT_USER}
      echo "#{VAGRANT_USER} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/99-user
      chmod 0440 /etc/sudoers.d/99-user

      # Setup SSH key for both vagrant and the configured user
      if [ -f /tmp/id_ed25519.pub ]; then
        mkdir -p /home/vagrant/.ssh
        grep -qF "$(cat /tmp/id_ed25519.pub)" /home/vagrant/.ssh/authorized_keys 2>/dev/null || cat /tmp/id_ed25519.pub >> /home/vagrant/.ssh/authorized_keys
        chmod 700 /home/vagrant/.ssh
        chmod 600 /home/vagrant/.ssh/authorized_keys
        chown -R vagrant:vagrant /home/vagrant/.ssh

        mkdir -p /home/#{VAGRANT_USER}/.ssh
        grep -qF "$(cat /tmp/id_ed25519.pub)" /home/#{VAGRANT_USER}/.ssh/authorized_keys 2>/dev/null || cat /tmp/id_ed25519.pub >> /home/#{VAGRANT_USER}/.ssh/authorized_keys
        chmod 700 /home/#{VAGRANT_USER}/.ssh
        chmod 600 /home/#{VAGRANT_USER}/.ssh/authorized_keys
        chown -R #{VAGRANT_USER}:#{VAGRANT_USER} /home/#{VAGRANT_USER}/.ssh
      fi
    SHELL

    # Run Ansible playbook for testing
    fedora.vm.provision 'ansible' do |ansible|
      ansible.playbook = ENV.fetch('ANSIBLE_PLAYBOOK', 'local.yml')
      ansible.groups = {
        'workstations' => ['fedora']
      }
      ansible.extra_vars = {
        ansible_python_interpreter: '/usr/bin/python3',
        ansible_user: VAGRANT_USER,
        user: { name: VAGRANT_USER, group: VAGRANT_USER, home: "/home/#{VAGRANT_USER}", shell: '/usr/bin/zsh' }
      }
      ansible.tags = ENV['ANSIBLE_TAGS'] || 'system'
      ansible.verbose = ENV['ANSIBLE_VERBOSE'] == 'true'
      ansible.raw_arguments = ['--check'] if ENV['ANSIBLE_CHECK']
    end
  end
end

# rubocop:enable Metrics/BlockLength

# Usage Examples:
#
# Basic testing:
#   vagrant up almalinux
#   vagrant up fedora
#
# Test with specific tags:
#   ANSIBLE_TAGS="system" vagrant up fedora
#   ANSIBLE_TAGS="base,networking" vagrant up fedora
#   ANSIBLE_TAGS="base,network" vagrant up almalinux
#
# Test with specific playbook:
#   ANSIBLE_PLAYBOOK="playbooks/workstation.yml" vagrant up fedora
#
# Test with specific Fedora box (e.g. Rawhide, F43, or custom):
#   FEDORA_BOX="fedora/41-cloud-base" vagrant up fedora
#
# Run in check mode (dry-run):
#   ANSIBLE_CHECK=true vagrant up fedora
#
# Enable verbose output:
#   ANSIBLE_VERBOSE=true vagrant up fedora
#
# Test both distributions:
#   vagrant up almalinux fedora
#
# Re-run provisioning after changes:
#   vagrant provision fedora
#   vagrant provision almalinux
