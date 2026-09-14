# frozen_string_literal: true

require "lipgloss"

# Terminal styling theme for the Playbook Composer TUI.
#
# Provides a consistent set of Lipgloss styles for all UI elements.
# Color codes are 256-color ANSI escape sequences (as strings).
#
# Color Reference:
# - 208: Orange (used for borders, headers, info)
# - 220: Yellow (used for selected items)
# - 240: Dark gray (used for unselected items)
# - 39: Light blue (used for variable keys)
# - 78: Green (used for variable values)
#
# @example Using theme styles
#   Theme::HEADER.render("Step 1: Select Scenario")
#   Theme::BORDER.render(content)
#
module Theme
  # Style for main content border with rounded corners.
  #
  # Uses orange (208) border color with 1px vertical and 2px horizontal padding.
  # Applied to the main view container to create a framed appearance.
  #
  # @return [Lipgloss::Style] style with rounded border, orange foreground, padding
  # @see Lipgloss::Style#border
  # @see Lipgloss::Style#border_foreground
  # @see Lipgloss::Style#padding
  BORDER = Lipgloss::Style.new.border(:rounded).border_foreground("208").padding(1, 2)

  # Style for section headers.
  #
  # Bold text with orange (208) foreground and bottom margin for spacing.
  # Used for step titles and section headings.
  #
  # @return [Lipgloss::Style] style with bold, orange foreground, bottom margin
  # @see Lipgloss::Style#bold
  # @see Lipgloss::Style#foreground
  # @see Lipgloss::Style#margin_bottom
  HEADER = Lipgloss::Style.new.bold(true).foreground("208").margin_bottom(1)

  # Style for selected role items in the list.
  #
  # Yellow (220) foreground with bold emphasis for visual selection highlight.
  # Applied to the currently cursor-selected role.
  #
  # @return [Lipgloss::Style] style with yellow foreground, bold
  # @see Lipgloss::Style#foreground
  # @see Lipgloss::Style#bold
  ROLE_SELECTED = Lipgloss::Style.new.foreground("220").bold(true)

  # Style for unselected role items in the list.
  #
  # Dark gray (240) foreground for subdued appearance.
  # Applied to roles that are not currently selected.
  #
  # @return [Lipgloss::Style] style with dark gray foreground
  # @see Lipgloss::Style#foreground
  ROLE_UNSELECTED = Lipgloss::Style.new.foreground("240")

  # Style for variable keys in the variables review.
  #
  # Light blue (39) foreground for key names.
  # Provides visual distinction from variable values.
  #
  # @return [Lipgloss::Style] style with light blue foreground
  # @see Lipgloss::Style#foreground
  VAR_KEY = Lipgloss::Style.new.foreground("39")

  # Style for variable values in the variables review.
  #
  # Green (78) foreground for value display.
  # Complements the key styling for pair visualization.
  #
  # @return [Lipgloss::Style] style with green foreground
  # @see Lipgloss::Style#foreground
  VAR_VALUE = Lipgloss::Style.new.foreground("78")

  # Style for informational text and help hints.
  #
  # Orange (208) foreground, consistent with headers and borders.
  # Used for keyboard shortcut hints at the bottom of each view.
  #
  # @return [Lipgloss::Style] style with orange foreground
  # @see Lipgloss::Style#foreground
  INFO = Lipgloss::Style.new.foreground("208")
end
