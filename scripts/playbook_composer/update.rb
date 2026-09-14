class PlaybookModel
  def update(msg)
    if msg.is_a?(Bubbletea::KeyMessage)
      case msg.to_s
      when "q", "ctrl+c"
        return [self, Bubbletea::QuitCommand.new]
      when "backspace"
        if self.step > 1 && self.step < 5
          self.step -= 1
          self.cursor = 0
        end
        return [self, nil]
      end
    end

    case self.step
    when 1
      update_scenarios(msg)
    when 2
      update_roles(msg)
    when 3
      update_variables(msg)
    when 4
      update_review(msg)
    when 5
      update_execute(msg)
    else
      [self, nil]
    end
  end
end
