# frozen_string_literal: true

class PlaybookModel
  # Pre-defined scenarios for quick playbook configuration.
  #
  # Each scenario provides a curated set of roles for common use cases.
  # Selecting a scenario pre-selects its roles in the role customization step.
  #
  # @type [Array<Hash{Symbol=>String,Array<String>}>] array of scenario definitions
  # @return [Hash] each scenario has :name, :desc, :roles keys
  SCENARIOS = [
    {
      name: "Full Workstation (Desktop, Containers, AI Agents)",
      desc: "Installs a complete dev environment including VS Code, Podman, and AI tools.",
      roles: %w[base desktop containerd coding_agents dotfiles],
    },
    {
      name: "Minimal Headless Server",
      desc: "Base OS configurations, tuning, and dotfiles only.",
      roles: %w[base dotfiles hardware],
    },
    {
      name: "LLMOps Local Platform",
      desc: "Deploys local LLM orchestration: Ollama, Dify, and Langfuse.",
      roles: %w[base containerd ai_ollama ai_dify ai_langfuse],
    },
    {
      name: "Custom (Start Blank)",
      desc: "Manually select individual roles in the next step.",
      roles: [],
    },
  ].freeze

  # Handle keyboard input for scenario selection (Step 1).
  #
  # @param msg [Bubbletea::Message] the incoming message
  # @return [Array(PlaybookModel, nil)] updated model with no command
  def update_scenarios(msg)
    if msg.is_a?(Bubbletea::KeyMessage)
      case msg.to_s
      # Move cursor up (with bounds checking)
      when "up", "k"
        self.cursor -= 1 if cursor.positive?
      # Move cursor down (with bounds checking)
      when "down", "j"
        self.cursor += 1 if cursor < SCENARIOS.length - 1
      # Select scenario and advance to step 2
      when "enter"
        scenario = SCENARIOS[cursor]
        # Reset all role selections
        selected.each_key { |k| selected[k] = false }

        # Pre-select the roles defined in the scenario
        scenario[:roles].each do |r_name|
          selected[r_name] = true if selected.key?(r_name)
        end

        # Move to role customization step
        self.step = 2
        self.cursor = 0
      end
    end
    [self, nil]
  end

  # Render the scenario selection view (Step 1).
  #
  # Displays all available scenarios in a scrollable list with
  # the cursor position highlighted. Shows description for the
  # currently selected scenario.
  #
  # @return [String] the rendered view content
  def view_scenarios
    out = "#{Theme::HEADER.render('Step 1: Choose a Pre-defined Scenario')}\n\n"

    # Render each scenario in the list
    SCENARIOS.each_with_index do |scen, i|
      cursor_char = (cursor == i) ? ">" : " "

      line = "#{cursor_char} #{scen[:name]}"
      if cursor == i
        # Highlight selected scenario
        out += "#{Theme::ROLE_SELECTED.render(line)}\n"
        # Show description for selected scenario
        out += "#{Theme::ROLE_UNSELECTED.render("    #{scen[:desc]}")}\n\n"
      else
        # Normal rendering for unselected scenarios
        out += "#{Theme::ROLE_UNSELECTED.render(line)}\n\n"
      end
    end

    # Add keyboard shortcut hints
    out += Theme::INFO.render("↑/k: up • ↓/j: down • enter: select & customize • q: quit")
    out
  end
end
