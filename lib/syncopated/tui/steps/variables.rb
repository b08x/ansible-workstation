# frozen_string_literal: true

class PlaybookModel
  # Handle keyboard input for variables review (Step 3).
  #
  # Allows navigating the variables list. Variable editing is
  # currently a placeholder (marked with 'e' key).
  #
  # @param msg [Bubbletea::Message] the incoming message
  # @return [Array(PlaybookModel, nil)] updated model with no command
  def update_variables(msg)
    keys = vars.keys

    if msg.is_a?(Bubbletea::KeyMessage)
      case msg.to_s
      # Move cursor up (with bounds checking)
      when "up", "k"
        self.cursor -= 1 if cursor.positive?
      # Move cursor down (with bounds checking)
      when "down", "j"
        self.cursor += 1 if cursor < keys.length - 1
      when "e"
        # TODO: Since full Bubbles::TextInput integration requires complex event routing,
        # we mark it as a placeholder for this iteration.
        # Future: implement variable editing with text input
      # Generate YAML and advance to review step
      when "enter"
        generate_yaml
        self.step = 4
        self.cursor = 0
      end
    end
    [self, nil]
  end

  # Render the variables review view (Step 3).
  #
  # Displays all variables from inventory in a scrollable list.
  # Each variable is shown as key: value on a separate line.
  #
  # @return [String] the rendered view content
  def view_variables
    out = "#{Theme::HEADER.render('Step 3: Review Variables')}\n\n"
    keys = vars.keys

    if keys.empty?
      # Show message if no variables found
      out += "No editable variables found.\n"
    else
      # Render each variable as key: value
      keys.each_with_index do |k, i|
        cursor_char = (cursor == i) ? ">" : " "
        v = vars[k]
        line = "#{cursor_char} #{k}: #{v}"
        out += if cursor == i
          # Highlight cursor position
          "#{Theme::ROLE_SELECTED.render(line)}\n"
        else
          "#{Theme::ROLE_UNSELECTED.render(line)}\n"
        end
      end
    end

    # Add keyboard shortcut hints
    out += "\n#{Theme::INFO.render('↑/k: up • ↓/j: down • e: edit (WIP) • enter: next • backspace: back • q: quit')}"
    out
  end
end
