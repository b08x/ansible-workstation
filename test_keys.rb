require 'bubbletea'

class TestModel
  include Bubbletea::Model

  def init; [self, nil]; end

  def update(msg)
    case msg
    when Bubbletea::KeyMessage
      return [self, Bubbletea.quit] if msg.to_s == "q"
      @last_key = "'#{msg.to_s}' (space? #{msg.space?})"
    end
    [self, nil]
  end

  def view
    "Last key pressed: #{@last_key}\nPress q to quit"
  end
end

Bubbletea.run(TestModel.new)
