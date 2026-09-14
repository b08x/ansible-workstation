#!/usr/bin/env ruby
# frozen_string_literal: true

require "tty-prompt"
require "yaml"
require "nexo_ai"

module Syncopated
  module Wizard
    class BuildImageWorkflow < Nexo::Workflow
      def call(payload)
        emit(:started, components: payload[:components])

        playbook = checkpoint(:build_playbook_structure) do
          [
            {
              "name" => "Build Custom OS Image",
              "hosts" => "localhost",
              "become" => true,
              "vars" => {
                "osbuild_components" => payload[:components],
                "blueprint_name" => payload[:image_name],
                "use_blueprint_template" => true,
              },
              "tasks" => [
                {
                  "include_role" => { "name" => "b08x.rhel_builder.osbuild" },
                },
              ],
            },
          ]
        end

        checkpoint(:write_playbook) do
          File.write(payload[:filename], playbook.to_yaml)
        end

        emit(:finished, filename: payload[:filename])
        { "filename" => payload[:filename], "status" => "success" }
      end
    end

    class CLI
      class << self
        def start
          command = ARGV.shift || "provision"

          case command
          when "provision"
            provision_host
          when "build_image", "build-image"
            build_image
          else
            puts "Unknown command: #{command}"
            puts "Available commands: provision, build_image"
            exit 1
          end
        end

        private

        def provision_host
          prompt = TTY::Prompt.new(active_color: :cyan)
          prompt.puts "🚀 \e[36mWelcome to the Syncopated Workstation Provisioner\e[0m"
          prompt.puts "Analyzing system capabilities..."

          is_ostree = File.exist?("/run/ostree-booted")
          has_nvidia = File.exist?("/proc/driver/nvidia/version")

          prompt.puts "Detected OSTree: #{is_ostree ? 'Yes' : 'No'}"
          prompt.puts "Detected NVIDIA GPU: #{has_nvidia ? 'Yes' : 'No'}"
          prompt.puts ""

          choices = [
            { name: "Base OS & Tuning (Recommended)", value: "b08x.devworkstation.base" },
            { name: "Desktop Environment (VS Code, UI)", value: "b08x.devworkstation.desktop" },
            { name: "Podman Container Stack", value: "b08x.devworkstation.containerd" },
            { name: "Libvirt Virtualization", value: "b08x.devworkstation.libvirt" },
            { name: "Network Configuration", value: "b08x.devworkstation.networking" },
            { name: "Coding Agents (Antigravity, Claude, Crush)", value: "b08x.devworkstation.coding_agents" },
            { name: "Local LLMOps (Ollama, Difify, Langfuse)", value: "b08x.llmops.run" },
          ]

          selected_roles = prompt.multi_select("Select the components you want to provision on this host:", choices, min: 1)

          tasks = selected_roles.map do |role_name|
            { "include_role" => { "name" => role_name } }
          end

          File.write("dynamic_run.yml", tasks.to_yaml)
          prompt.ok("Playbook generated successfully with #{tasks.count} components. Handing off to Ansible...")
        end

        def build_image
          prompt = TTY::Prompt.new(active_color: :cyan)
          prompt.puts "📦 \e[36mWelcome to the OSBuild Image Generator\e[0m"

          image_name = prompt.ask("Enter a name for your custom image:", default: "custom-workstation")
          filename = "#{image_name}_build.yml"

          osbuild_choices = [
            { name: "Base Workstation (core)", value: "core" },
            { name: "GNOME Desktop + Extras (desktop)", value: "desktop" },
            { name: "NVIDIA Drivers", value: "nvidia" },
            { name: "Audio Production Stack", value: "audio" },
            { name: "Virtualization Host", value: "virtualization" },
          ]

          selected_components = prompt.multi_select("Select the osbuild components to include in the image:",
            osbuild_choices, min: 1)

          prompt.puts "Starting Nexo workflow to generate playbook..."

          run = BuildImageWorkflow.run(
            image_name: image_name,
            components: selected_components,
            filename: filename
          )

          if run.status == "done"
            prompt.ok("Playbook successfully generated: #{run.result['filename']}")
          else
            prompt.error("Workflow failed with status: #{run.status}")
          end
        end
      end
    end
  end
end
