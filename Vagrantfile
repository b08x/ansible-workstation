#!/usr/bin/env ruby
# frozen_string_literal: true

ENV["VAGRANT_DEFAULT_PROVIDER"] = "libvirt"

# Configuration variables
ALMALINUX_HOSTNAME = "almalinux-test.syncopated.dev"
ARCH_HOSTNAME = "arch-test.syncopated.dev"

DEV_USER = ENV.fetch("USER", nil)

# rubocop:disable Metrics/BlockLength
Vagrant.configure("2") do |config|
  # Global SSH configuration
  config.ssh.insert_key = false
  config.ssh.forward_agent = true

  # Rocky Linux 9 VM for testing
  config.vm.define "almalinux", primary: true do |almalinux|
    almalinux.vm.box = "almalinux/10"
    almalinux.vm.hostname = ALMALINUX_HOSTNAME

    almalinux.vm.network :private_network,
      ip: "192.168.122.10",
      libvirt__network_name: "default"

    almalinux.vm.provider :libvirt do |libvirt|
      libvirt.memory = 8192
      libvirt.uri = "qemu:///system"
      libvirt.cpus = 8
      libvirt.nested = true
      libvirt.disk_bus = "virtio"
      libvirt.cpu_mode = "host-passthrough"
      libvirt.nic_model_type = "virtio"
      libvirt.disk_driver cache: "writeback"
      libvirt.machine_virtual_size = 50
      libvirt.graphics_type = "spice"
      libvirt.video_type = "qxl"
    end

    # Sync the entire project for testing
    almalinux.vm.synced_folder ".", "/vagrant",
      type: "rsync",
      rsync__exclude: [".git/", "*.swp", ".venv/", ".vagrant/"]

    # Copy SSH key for testing
    almalinux.vm.provision "file",
      source: "~/.ssh/id_ed25519.pub",
      destination: "/tmp/id_ed25519.pub"

    # Bootstrap system for testing
    almalinux.vm.provision "shell", inline: <<-SHELL
      # Update system
	    dnf config-manager --set-enabled crb
      # Install required packages
      dnf install -y --setopt=timeout=5 --setopt=retries=2 epel-release
      dnf install -y --setopt=timeout=5 --setopt=retries=2 python3 python3-pip ansible-core git curl make zsh
      dnf install -y --setopt=timeout=5 --setopt=retries=2 ansible-collection-ansible-posix ansible-collection-ansible-utils

      dnf clean all && dnf update -y --setopt=timeout=5 --setopt=retries=2

      # Setup SSH key
      mkdir -p /home/vagrant/.ssh
      cat /tmp/id_ed25519.pub >> /home/vagrant/.ssh/authorized_keys
      chmod 600 /home/vagrant/.ssh/authorized_keys
      chown vagrant:vagrant /home/vagrant/.ssh/authorized_keys

      # Create test user that matches inventory
      useradd -m -s /usr/bin/zsh b08x || true
      usermod -aG wheel b08x
      mkdir -p /home/b08x/.ssh
      cat /tmp/id_ed25519.pub >> /home/b08x/.ssh/authorized_keys
      chmod 600 /home/b08x/.ssh/authorized_keys
      chown b08x:b08x /home/b08x/.ssh/authorized_keys
      echo "b08x ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/99-user
    SHELL

    # Run Ansible playbook for testing
    almalinux.vm.provision "ansible" do |ansible|
      ansible.playbook = "playbooks/site.yml"
      ansible.groups = {
        "workstations" => ["almalinux"],
      }
      ansible.extra_vars = {
        ansible_python_interpreter: "/usr/bin/python3",
        ansible_user: "b08x",
        user: { name: "b08x", group: "b08x", home: "/home/b08x", shell: "/usr/bin/zsh" },
        # Override variables for testing
        use_containers: "false",
        use_kvm: "false",
      }
      # ansible.tags = ENV['ANSIBLE_TAGS'] || 'cargo'
      ansible.verbose = ENV["ANSIBLE_VERBOSE"] || false
      # ansible.skip_tags = 'libvirt,containerd'
      ansible.raw_arguments = ["--check"] if ENV["ANSIBLE_CHECK"]
    end
  end

  # Optional Arch Linux VM for comparison testing
  # config.vm.define 'arch', autostart: false do |arch|
  #   arch.vm.box = 'archlinux/archlinux'
  #   arch.vm.hostname = ARCH_HOSTNAME

  #   arch.vm.network :private_network,
  #                   ip: '192.168.122.11',
  #                   libvirt__network_name: 'default'

  #   arch.vm.provider :libvirt do |libvirt|
  #     libvirt.uri = 'qemu:///system'
  #     libvirt.memory = 2048
  #     libvirt.cpus = 2
  #     libvirt.nested = true
  #     libvirt.disk_bus = 'virtio'
  #     libvirt.cpu_mode = 'host-passthrough'
  #     libvirt.nic_model_type = 'virtio'
  #     libvirt.disk_driver cache: 'writeback'
  #     libvirt.machine_virtual_size = 50
  #   end

  #   arch.vm.synced_folder '.', '/vagrant',
  #                         type: 'rsync',
  #                         rsync__exclude: ['.git/', '*.swp', '.venv/', '.vagrant/']

  #   arch.vm.provision 'file',
  #                     source: '~/.ssh/id_ed25519.pub',
  #                     destination: '/tmp/id_ed25519.pub'

  #   arch.vm.provision 'shell', inline: <<-SHELL
  #     # Update system
  #     pacman -Syu --noconfirm

  #     # Install required packages
  #     pacman -Sy --noconfirm python python-pip ansible git

  #     # Setup SSH key
  #     mkdir -p /home/vagrant/.ssh
  #     cat /tmp/id_ed25519.pub >> /home/vagrant/.ssh/authorized_keys
  #     chmod 600 /home/vagrant/.ssh/authorized_keys
  #     chown vagrant:vagrant /home/vagrant/.ssh/authorized_keys
  #   SHELL

  #   # Run Ansible playbook
  #   arch.vm.provision 'ansible' do |ansible|
  #     ansible.playbook = 'site.yml'
  #     ansible.groups = {
  #       'workstations' => ['arch']
  #     }
  #     ansible.extra_vars = {
  #       ansible_python_interpreter: '/usr/bin/python3',
  #       ansible_user: 'vagrant',
  #       user: { name: 'vagrant', group: 'vagrant', home: '/home/vagrant', shell: '/bin/bash' },
  #       use_docker: 'false',
  #       use_libvirt: 'false',
  #       window_manager: 'i3',
  #       rvm_install: false
  #     }
  #     ansible.tags = ENV['ANSIBLE_TAGS'] || 'base,ssh,shell'
  #     ansible.verbose = ENV['ANSIBLE_VERBOSE'] || false
  #     ansible.raw_arguments = ['--check'] if ENV['ANSIBLE_CHECK']
  #   end
  # end
end

# rubocop:enable Metrics/BlockLength

# Usage Examples:
#
# Basic testing:
#   vagrant up almalinux
#
# Test with specific tags:
#   ANSIBLE_TAGS="base,network" vagrant up almalinux
#
# Run in check mode (dry-run):
#   ANSIBLE_CHECK=true vagrant up almalinux
#
# Enable verbose output:
#   ANSIBLE_VERBOSE=true vagrant up almalinux
#
# Test both distributions:
#   vagrant up almalinux arch
#
# Re-run provisioning after changes:
#   vagrant provision almalinux
