require 'lipgloss'

module Theme
  BORDER = Lipgloss::Style.new.border(:rounded).border_foreground("208").padding(1, 2)
  HEADER = Lipgloss::Style.new.bold(true).foreground("208").margin_bottom(1)
  ROLE_SELECTED = Lipgloss::Style.new.foreground("220").bold(true)
  ROLE_UNSELECTED = Lipgloss::Style.new.foreground("240")
  VAR_KEY = Lipgloss::Style.new.foreground("39")
  VAR_VALUE = Lipgloss::Style.new.foreground("78")
  INFO = Lipgloss::Style.new.foreground("208")
end
