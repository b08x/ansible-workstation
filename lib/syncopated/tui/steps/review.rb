# frozen_string_literal: true

require "glamour"
require "bubbles"

class PlaybookModel
  # Generate the Ansible playbook YAML from selected roles and variables.
  #
  # Creates a playbook structure with the selected roles as include_role tasks.
  # Also initializes the viewport for scrollable YAML preview.
  #
  # @return [void] sets yaml_output and initializes @viewport
  # @see PlaybookModel#yaml_output
  def generate_yaml
    # Build include_role tasks for each selected role
    tasks = []
    selected.select { |_k, v| v }.each_key do |role_name|
      tasks << { "include_role" => { "name" => role_name } }
    end

    # Construct the full playbook payload as a YAML array (list of plays)
    payload = [
{
  "name" => "Dynamic Bootstrap",
  "hosts" => hostname,
  "connection" => "local",
  "vars" => vars,
  "tasks" => tasks,
},
]
    self.yaml_output = payload.to_yaml

    # Initialize viewport for scrollable YAML preview
    #
    # Uses Bubbles::Viewport for scrollable content display.
    # Width of 80 characters fits typical terminals.
    # Height of 15 lines provides reasonable preview window.
    #
    # @see Bubbles::Viewport
    @viewport = Bubbles::Viewport.new(width: 80, height: 15)
    begin
      # Render YAML with markdown formatting using Glamour
      # Wraps the YAML in a code block for markdown rendering
      @viewport.content = Glamour::Renderer.new(style: "dark").render("```yaml\n#{yaml_output}\n```")
    rescue
      # Fallback to plain YAML if markdown rendering fails
      @viewport.content = yaml_output
    end
  end

  # Handle keyboard input for playbook review (Step 4).
  #
  # @param msg [Bubbletea::Message] the incoming message
  # @return [Array(PlaybookModel, Bubbletea::Command, nil)] updated model and optional command
  def update_review(msg)
    if msg.is_a?(Bubbletea::KeyMessage)
      case msg.to_s
      # Execute the playbook and advance to step 5
      when "enter"
        self.step = 5
        self.running = true
        return [self, start_execute_cmd]
      end
    end

    # Delegate scroll events to viewport for YAML preview scrolling
    @viewport, cmd = @viewport.update(msg) if @viewport
    [self, cmd]
  end

  # Render the playbook review view (Step 4).
  #
  # Displays the generated YAML playbook in a scrollable viewport.
  # Shows either the styled viewport or plain YAML as fallback.
  #
  # @return [String] the rendered view content
  def view_review
    out = "#{Theme::HEADER.render('Step 4: Review Playbook')}\n\n"

    # Display either the viewport (for scrollable preview) or plain YAML
    out += if @viewport
      @viewport.view
    else
      yaml_output
    end

    # Add keyboard shortcut hints
    out += "\n\n#{Theme::INFO.render('enter: execute • backspace: back • ↑/↓: scroll • q: quit')}"
    out
  end
end
