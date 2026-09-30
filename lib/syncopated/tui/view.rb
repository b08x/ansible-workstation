# frozen_string_literal: true

class PlaybookModel
  # Render the current view based on the application step.
  #
  # This is the Elm Architecture view function that generates
  # the string representation of the current UI state.
  # It delegates to step-specific view renderers.
  #
  # @return [String] the rendered view content wrapped in a border
  # @see Bubbletea::Model#view
  def view
    out = ""
    # Delegate to step-specific view renderers
    case step
    when 1
      # Step 1: Scenario selection view
      out = view_scenarios
    when 2
      # Step 2: Role customization view
      out = view_roles
    when 3
      # Step 3: Variables review view
      out = view_variables
    when 4
      # Step 4: Playbook review view
      out = view_review
    when 5
      # Step 5: Execution view
      out = view_execute
    end

    # Wrap everything in a nice rounded border for consistent appearance
    Theme::BORDER.render(out)
  end
end
