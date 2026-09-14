#!/usr/bin/env ruby
# frozen_string_literal: true

require "tty-prompt"
require "yaml"
require_relative "config"
require_relative "agent"

module Syncopated
  module Wizard
    class CLI
      class << self
        def start
          command = ARGV.shift || "provision"

          case command
          when "provision"
            provision_host
          when "build_image", "build-image"
            build_image
          when "config"
            Syncopated::Config.configure_llm(TTY::Prompt.new(active_color: :cyan), force: true)
          else
            puts "Unknown command: #{command}"
            puts "Available commands: provision, build_image, config"
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

          selected_roles = prompt.multi_select("Select the components you want to provision on this host:", choices,
            min: 1)

          tasks = selected_roles.map do |role_name|
            { "include_role" => { "name" => role_name } }
          end

          File.write("dynamic_run.yml", tasks.to_yaml)
          prompt.ok("Playbook generated successfully with #{tasks.count} components. Handing off to Ansible...")
        end

        def build_image
          prompt = TTY::Prompt.new(active_color: :cyan)
          Syncopated::Config.configure_llm(prompt)

          prompt.puts "📦 \e[36mWelcome to the AI-Assisted OSBuild Image Generator\e[0m"
          prompt.puts "Describe the custom appliance or OS image you want to build."
          prompt.puts "(e.g., 'I need a kiosk ISO installer for a microservice based application')\n\n"

          initial_request = prompt.ask("Your request:")
          return if initial_request.nil? || initial_request.strip.empty?

          prompt.puts "\n\e[33mInitializing Syncopated::Agent with :syncopated skill...\e[0m\n"
          agent = Syncopated::Agent.new(model: ENV.fetch("NEXO_MODEL", "gemini-2.5-pro"))
          chat = agent.chat

          response = chat.prompt(initial_request)

          loop do
            prompt.puts "\n🤖 \e[32mAgent:\e[0m\n#{response.content}"

            # Allow exiting if the agent thinks it's done or user wants to stop
            if response.content.downcase.include?("playbook generated") || response.content.downcase.include?("written the playbook")
              break
            end

            user_input = prompt.ask("\n👤 \e[36mYou (type 'exit' to quit):\e[0m")
            break if user_input.nil? || user_input.strip.downcase == "exit"

            response = chat.prompt(user_input)
          end

          prompt.ok("\nImage builder workflow completed.")
        end
      end
    end
  end
end
