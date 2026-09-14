class PlaybookModel
  def view
    out = ""
    case self.step
    when 1
      out = view_scenarios
    when 2
      out = view_roles
    when 3
      out = view_variables
    when 4
      out = view_review
    when 5
      out = view_execute
    end
    
    # Wrap everything in a nice rounded border
    Theme::BORDER.render(out)
  end
end
