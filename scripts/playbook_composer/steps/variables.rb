class PlaybookModel
  def update_variables(msg)
    keys = self.vars.keys
    
    if msg.is_a?(Bubbletea::KeyMessage)
      case msg.to_s
      when "up", "k"
        self.cursor -= 1 if self.cursor > 0
      when "down", "j"
        self.cursor += 1 if self.cursor < keys.length - 1
      when "e"
        # Since full Bubbles::TextInput integration requires complex event routing,
        # we mark it as a placeholder for this iteration.
      when "enter"
        generate_yaml
        self.step = 4
        self.cursor = 0
      end
    end
    [self, nil]
  end

  def view_variables
    out = Theme::HEADER.render("Step 3: Review Variables") + "\n\n"
    keys = self.vars.keys
    
    if keys.empty?
      out += "No editable variables found.\n"
    else
      keys.each_with_index do |k, i|
        cursor_char = self.cursor == i ? ">" : " "
        v = self.vars[k]
        line = "#{cursor_char} #{k}: #{v}"
        if self.cursor == i
          out += Theme::ROLE_SELECTED.render(line) + "\n"
        else
          out += Theme::ROLE_UNSELECTED.render(line) + "\n"
        end
      end
    end
    
    out += "\n" + Theme::INFO.render("↑/k: up • ↓/j: down • e: edit (WIP) • enter: next • backspace: back • q: quit")
    out
  end
end
