# frozen_string_literal: true

class PlaybookModel
  # Handle keyboard input for role customization (Step 2).
  #
  # Allows navigating the role list and toggling individual role selections.
  #
  # @param msg [Bubbletea::Message] the incoming message
  # @return [Array(PlaybookModel, nil)] updated model with no command
  def update_roles(msg)
    if msg.is_a?(Bubbletea::KeyMessage)
      case msg.to_s
      # Move cursor up (with bounds checking)
      when "up", "k"
        self.cursor -= 1 if cursor.positive?
      # Move cursor down (with bounds checking)
      when "down", "j"
        self.cursor += 1 if cursor < roles.length - 1
      # Toggle selection for the current role
      when " ", "space"
        role_name = roles[cursor][:name]
        selected[role_name] = !selected[role_name]
      # Advance to variables review step
      when "enter"
        self.step = 3
        self.cursor = 0
      end
    end
    [self, nil]
  end

  # Render the role customization view (Step 2).
  #
  # Displays a paginated list of roles with selection checkboxes.
  # Shows 20 roles at a time with the current cursor position highlighted.
  # Selected roles show a filled circle (●), unselected show empty (○).
  #
  # @return [String] the rendered view content
  def view_roles
    out = "#{Theme::HEADER.render('Step 2: Customize Roles')}\n\n"

    # Calculate visible range (20 roles per page, centered on cursor)
    start_idx = [0, cursor - 10].max
    end_idx = [roles.length - 1, start_idx + 20].min

    # Render visible roles
    roles[start_idx..end_idx].each_with_index do |role, i|
      actual_idx = start_idx + i
      cursor_char = (cursor == actual_idx) ? ">" : " "
      selected_char = selected[role[:name]] ? "●" : "○"

      line = "#{cursor_char} #{selected_char} #{role[:name]} (#{role[:tasks_count]} tasks)"

      if cursor == actual_idx
        # Highlight cursor position
        out += "#{Theme::ROLE_SELECTED.render(line)}\n"
        # Show description for cursor position
        out += "#{Theme::ROLE_UNSELECTED.render("      #{role[:desc]}")}\n"
      else
        out += "#{Theme::ROLE_UNSELECTED.render(line)}\n"
      end
    end

    # Add keyboard shortcut hints
    out += "\n#{Theme::INFO.render('↑/k: up • ↓/j: down • space: toggle • enter: next • q: quit')}"
    out
  end
end
