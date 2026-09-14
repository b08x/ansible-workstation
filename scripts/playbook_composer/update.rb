# frozen_string_literal: true

class PlaybookModel
  # Handle incoming messages and update model state accordingly.
  #
  # This is the core of the Elm Architecture update function.
  # It delegates to step-specific handlers based on the current step.
  #
  # @param msg [Bubbletea::Message] the incoming message to process
  # @return [Array(PlaybookModel, Bubbletea::Command, nil)] updated model and optional command
  # @see Bubbletea::Model#update
  def update(msg)
    # Handle global keyboard shortcuts that apply to all steps
    if msg.is_a?(Bubbletea::KeyMessage)
      case msg.to_s
      # Quit the application on 'q' or Ctrl+C
      when "q", "ctrl+c"
        return [self, Bubbletea::QuitCommand.new]
      # Go back to previous step (works for steps 2-4)
      when "backspace"
        if step > 1 && step < 5
          self.step -= 1
          self.cursor = 0
        end
        return [self, nil]
      end
    end

    # Delegate to step-specific update handlers
    case step
    when 1
      # Step 1: Scenario selection
      update_scenarios(msg)
    when 2
      # Step 2: Role customization
      update_roles(msg)
    when 3
      # Step 3: Variables review
      update_variables(msg)
    when 4
      # Step 4: Playbook review
      update_review(msg)
    when 5
      # Step 5: Playbook execution
      update_execute(msg)
    else
      # Unknown step - return self with no command
      [self, nil]
    end
  end
end
