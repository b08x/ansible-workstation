class PlaybookModel
  def update_roles(msg)
    if msg.is_a?(Bubbletea::KeyMessage)
      case msg.to_s
      when "up", "k"
        self.cursor -= 1 if self.cursor > 0
      when "down", "j"
        self.cursor += 1 if self.cursor < self.roles.length - 1
      when " ", "space"
        role_name = self.roles[self.cursor][:name]
        self.selected[role_name] = !self.selected[role_name]
      when "enter"
        self.step = 3
        self.cursor = 0
      end
    end
    [self, nil]
  end

  def view_roles
    out = Theme::HEADER.render("Step 2: Customize Roles") + "\n\n"
    
    start_idx = [0, self.cursor - 10].max
    end_idx = [self.roles.length - 1, start_idx + 20].min
    
    self.roles[start_idx..end_idx].each_with_index do |role, i|
      actual_idx = start_idx + i
      cursor_char = self.cursor == actual_idx ? ">" : " "
      selected_char = self.selected[role[:name]] ? "●" : "○"
      
      line = "#{cursor_char} #{selected_char} #{role[:name]} (#{role[:tasks_count]} tasks)"
      
      if self.cursor == actual_idx
        out += Theme::ROLE_SELECTED.render(line) + "\n"
        out += Theme::ROLE_UNSELECTED.render("      #{role[:desc]}") + "\n"
      else
        out += Theme::ROLE_UNSELECTED.render(line) + "\n"
      end
    end
    
    out += "\n" + Theme::INFO.render("↑/k: up • ↓/j: down • space: toggle • enter: next • q: quit")
    out
  end
end
