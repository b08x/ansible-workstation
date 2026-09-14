class PlaybookModel
  SCENARIOS = [
    {
      name: "Full Workstation (Desktop, Containers, AI Agents)",
      desc: "Installs a complete dev environment including VS Code, Podman, and AI tools.",
      roles: ["base", "desktop", "containerd", "coding_agents", "dotfiles"]
    },
    {
      name: "Minimal Headless Server",
      desc: "Base OS configurations, tuning, and dotfiles only.",
      roles: ["base", "dotfiles", "hardware"]
    },
    {
      name: "LLMOps Local Platform",
      desc: "Deploys local LLM orchestration: Ollama, Dify, and Langfuse.",
      roles: ["base", "containerd", "ai_ollama", "ai_dify", "ai_langfuse"]
    },
    {
      name: "Custom (Start Blank)",
      desc: "Manually select individual roles in the next step.",
      roles: []
    }
  ]

  def update_scenarios(msg)
    if msg.is_a?(Bubbletea::KeyMessage)
      case msg.to_s
      when "up", "k"
        self.cursor -= 1 if self.cursor > 0
      when "down", "j"
        self.cursor += 1 if self.cursor < SCENARIOS.length - 1
      when "enter"
        scenario = SCENARIOS[self.cursor]
        # Pre-select roles based on scenario
        self.selected.keys.each { |k| self.selected[k] = false }
        
        scenario[:roles].each do |r_name|
           self.selected[r_name] = true if self.selected.key?(r_name)
        end
        
        self.step = 2
        self.cursor = 0
      end
    end
    [self, nil]
  end

  def view_scenarios
    out = Theme::HEADER.render("Step 1: Choose a Pre-defined Scenario") + "\n\n"
    
    SCENARIOS.each_with_index do |scen, i|
      cursor_char = self.cursor == i ? ">" : " "
      
      line = "#{cursor_char} #{scen[:name]}"
      if self.cursor == i
        out += Theme::ROLE_SELECTED.render(line) + "\n"
        out += Theme::ROLE_UNSELECTED.render("    #{scen[:desc]}") + "\n\n"
      else
        out += Theme::ROLE_UNSELECTED.render(line) + "\n\n"
      end
    end
    
    out += Theme::INFO.render("↑/k: up • ↓/j: down • enter: select & customize • q: quit")
    out
  end
end
