#!/usr/bin/env ruby
# frozen_string_literal: true

# The Syncopated Workstation Provisioner interactive setup wizard.
# 
# This script provides a TUI interface for selecting which Ansible roles
# to provision on the current host. It detects system capabilities
# (OSTree, NVIDIA GPU) and generates a dynamic Ansible playbook.
#
# @example Running the wizard
#   ruby scripts/wizard.rb
#
require "tty-prompt"
require "yaml"

# Initialize TTY::Prompt with cyan active color for interactive selections
#
# @return [TTY::Prompt] configured prompt instance with cyan highlighting
prompt = TTY::Prompt.new(active_color: :cyan)

# Display welcome message with cyan color
#
# @return [void] outputs colored welcome message to terminal
prompt.puts "🚀 \e[36mWelcome to the Syncopated Workstation Provisioner\e[0m"
prompt.puts "Analyzing system capabilities..."

# Detect system capabilities for role compatibility checking
#
# In a real scenario, these would use sys-proctable gem or parse /proc directly.
# OSTree detection checks if running on an immutable Fedora variant.
#
# @return [Boolean] true if running on OSTree-based system
# @note Mock detection - checks for /run/ostree-booted existence
is_ostree = File.exist?("/run/ostree-booted")

# Detect NVIDIA GPU presence for GPU-accelerated roles
#
# @return [Boolean] true if NVIDIA driver is loaded
# @note Mock detection - checks for /proc/driver/nvidia/version existence
has_nvidia = File.exist?("/proc/driver/nvidia/version")

# Display detected hardware capabilities to user
prompt.puts "Detected OSTree: #{is_ostree ? 'Yes' : 'No'}"
prompt.puts "Detected NVIDIA GPU: #{has_nvidia ? 'Yes' : 'No'}"
prompt.puts ""

# Available Ansible roles for provisioning, mapped from AGENTS.md structure.
# 
# Each choice represents a collection role that can be provisioned.
# The value format follows the collection namespace: b08x.<collection>.<role>
#
# @return [Array<Hash{Symbol=>String}>] array of role choice hashes with name and value
# @see https://github.com/ansible/ansible-creator docs for role structure
choices = [
  { name: "Base OS & Tuning (Recommended)", value: "b08x.devworkstation.base" },
  { name: "Desktop Environment (VS Code, UI)", value: "b08x.devworkstation.desktop" },
  { name: "Podman Container Stack", value: "b08x.devworkstation.containerd" },
  { name: "Libvirt Virtualization", value: "b08x.devworkstation.libvirt" },
  { name: "Network Configuration", value: "b08x.devworkstation.networking" },
  { name: "Coding Agents (Antigravity, Claude, Crush)", value: "b08x.devworkstation.coding_agents" },
  { name: "Local LLMOps (Ollama, Difify, Langfuse)", value: "b08x.llmops.run" },
]

# Prompt user to select roles with multi-select interface.
# 
# Uses TTY::Prompt#multi_select which returns an array of selected values.
# The min: 1 option enforces at least one selection before proceeding.
#
# @param prompt [TTY::Prompt] the prompt instance
# @param message [String] the prompt message to display
# @param choices [Array<Hash>] the available choices
# @param min [Integer] minimum number of selections required
# @return [Array<String>] array of selected role names (value field from choices)
# @raise [TTY::Prompt::InputError] if user attempts to proceed with no selections
selected_roles = prompt.multi_select("Select the components you want to provision on this host:", choices, min: 1)

# Transform selected role names into Ansible include_role task structure.
# 
# Each selected role becomes an include_role task in the generated playbook.
# This follows Ansible's role inclusion pattern for dynamic playbook composition.
#
# @param selected_roles [Array<String>] array of fully-qualified role names
# @return [Array<Hash{String=>Hash{String=>String}}>] array of Ansible include_role tasks
# @example Generated task structure
#   [{"include_role" => {"name" => "b08x.devworkstation.base"}}]
tasks = selected_roles.map do |role_name|
  { "include_role" => { "name" => role_name } }
end

# Write the generated Ansible playbook to disk.
# 
# Creates dynamic_run.yml in the current directory with the selected roles.
# Uses YAML serialization via Array#to_yaml for proper Ansible format.
#
# @param filename [String] the output file path
# @param tasks [Array<Hash>] the Ansible task structure
# @return [Integer] number of bytes written
# @raise [Errno::EACCES] if file cannot be written to current directory
File.write("dynamic_run.yml", tasks.to_yaml)

# Notify user of successful generation and handoff to Ansible.
# 
# Uses TTY::Prompt#ok to display a success message with checkmark.
#
# @param message [String] the success message to display
# @return [void] outputs success message to terminal
prompt.ok("Playbook generated successfully with #{tasks.count} components. Handing off to Ansible...")
