require 'glamour'
require 'bubbles'

class PlaybookModel
  def generate_yaml
    tasks = []
    self.selected.select { |k, v| v }.each do |role_name, _|
      tasks << { "include_role" => { "name" => role_name } }
    end
    
    payload = [{
      "name" => "Dynamic Bootstrap",
      "hosts" => self.hostname,
      "connection" => "local",
      "vars" => self.vars,
      "tasks" => tasks
    }]
    self.yaml_output = payload.to_yaml
    
    # Initialize viewport for Step 3
    @viewport = Bubbles::Viewport.new(width: 80, height: 15)
    begin
      @viewport.content = Glamour::Renderer.new(style: "dark").render("```yaml\n#{self.yaml_output}\n```")
    rescue
      @viewport.content = self.yaml_output
    end
  end

  def update_review(msg)
    if msg.is_a?(Bubbletea::KeyMessage)
      case msg.to_s
      when "enter"
        self.step = 5
        self.running = true
        return [self, start_execute_cmd]
      end
    end
    
    # Delegate to viewport
    @viewport, cmd = @viewport.update(msg) if @viewport
    [self, cmd]
  end

  def view_review
    out = Theme::HEADER.render("Step 4: Review Playbook") + "\n\n"
    
    if @viewport
      out += @viewport.view
    else
      out += self.yaml_output
    end
    
    out += "\n\n" + Theme::INFO.render("enter: execute • backspace: back • ↑/↓: scroll • q: quit")
    out
  end
end
