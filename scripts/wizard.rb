#!/usr/bin/env ruby
# frozen_string_literal: true

require 'tty-prompt'
require 'yaml'

prompt = TTY::Prompt.new(active_color: :cyan)

prompt.puts "🚀 \e[36mWelcome to the Syncopated Workstation Provisioner\e[0m"
prompt.puts "Analyzing system capabilities..."

# Mock hardware detection - in a real scenario, use sys-proctable or check /proc
is_ostree = File.exist?("/run/ostree-booted")
has_nvidia = File.exist?("/proc/driver/nvidia/version")

prompt.puts "Detected OSTree: #{is_ostree ? 'Yes' : 'No'}"
prompt.puts "Detected NVIDIA GPU: #{has_nvidia ? 'Yes' : 'No'}"
prompt.puts ""

tasks = []

# Offer interactive menu to the user based on roles found in AGENTS.md
choices = [
  { name: 'Base OS & Tuning (Recommended)', value: 'b08x.devworkstation.base' },
  { name: 'Desktop Environment (VS Code, UI)', value: 'b08x.devworkstation.desktop' },
  { name: 'Podman Container Stack', value: 'b08x.devworkstation.containerd' },
  { name: 'Libvirt Virtualization', value: 'b08x.devworkstation.libvirt' },
  { name: 'Network Configuration', value: 'b08x.devworkstation.networking' },
  { name: 'Coding Agents (Antigravity, Claude, Crush)', value: 'b08x.devworkstation.coding_agents' },
  { name: 'Local LLMOps (Ollama, Difify, Langfuse)', value: 'b08x.llmops.run' }
]

selected_roles = prompt.multi_select("Select the components you want to provision on this host:", choices, min: 1)

# Generate Ansible include_role tasks for each selected module
selected_roles.each do |role_name|
  tasks << { "include_role" => { "name" => role_name } }
end

# Write the dynamic payload that Ansible will execute
File.write("dynamic_run.yml", tasks.to_yaml)

prompt.ok("Playbook generated successfully with #{tasks.count} components. Handing off to Ansible...")
