# frozen_string_literal: true

require "open3"
require "bubbles"

# Message sent when Ansible execution completes.
#
# Carries the combined output (stdout + stderr) and exit code
# from the ansible-playbook process.
#
# @attr output [String] combined stdout and stderr from the Ansible run
# @attr rc [Integer] exit status code from ansible-playbook
class ExecDoneMsg < Bubbletea::Message
  attr_accessor :output, :rc

  # Initialize a new execution completion message.
  #
  # @param output [String] combined output from stdout and stderr
  # @param rc [Integer] exit status code
  def initialize(output, rc)
    @output = output
    @rc = rc
  end
end

class PlaybookModel
  # Start the Ansible execution command.
  #
  # Writes the generated YAML to disk and runs ansible-playbook.
  # Uses Bubbletea.batch to run both the execution task and spinner concurrently.
  #
  # @return [Bubbletea::Command] batch command containing execution task and spinner tick
  # @see Bubbletea.batch
  # @see ExecDoneMsg
  def start_execute_cmd
    # Initialize spinner for visual feedback during execution
    # Uses the DOT spinner style from Bubbles
    @spinner ||= Bubbles::Spinner.new(spinner: Bubbles::Spinners::DOT)

    # Define the execution task as a lambda
    exec_task = lambda {
      # Write the generated YAML to disk
      File.write("dynamic_run.yml", yaml_output)
      # Capture ansible-playbook output using Open3
      stdout_str, stderr_str, status = Open3.capture3("ansible-playbook dynamic_run.yml")
      # Send completion message with combined output and exit code
      ExecDoneMsg.new("#{stdout_str}\n#{stderr_str}", status.exitstatus)
    }

    # Run both the execution task and spinner tick command concurrently
    Bubbletea.batch(exec_task, @spinner.tick)
  end

  # Handle messages during execution (Step 5).
  #
  # Processes ExecDoneMsg to capture output and exit code.
  # Updates spinner animation while execution is running.
  #
  # @param msg [Bubbletea::Message] the incoming message
  # @return [Array(PlaybookModel, Bubbletea::Command, nil)] updated model and optional command
  def update_execute(msg)
    @spinner ||= Bubbles::Spinner.new(spinner: Bubbles::Spinners::DOT)

    # Handle execution completion message
    if msg.is_a?(ExecDoneMsg)
      self.running = false
      self.output_lines = msg.output.split("\n")
      self.rc = msg.rc
      return [self, nil]
    end

    # Update spinner while execution is running
    if running
      @spinner, cmd = @spinner.update(msg)
      return [self, cmd]
    end

    [self, nil]
  end

  # Render the execution view (Step 5).
  #
  # Shows a spinner animation while execution is running.
  # Displays the exit code and last 15 lines of output when complete.
  #
  # @return [String] the rendered view content
  def view_execute
    out = "#{Theme::HEADER.render('Step 5: Execute Playbook')}\n\n"

    if running
      @spinner ||= Bubbles::Spinner.new(spinner: Bubbles::Spinners::DOT)
      # Show spinner animation with status message
      out += "#{@spinner.view} Running ansible-playbook... Please wait.\n"
    else
      # Execution complete - show result
      out += "Execution finished with code #{rc}\n\n"
      # Show last 15 lines of output for quick review
      tail = output_lines.last(15).join("\n")
      out += tail
    end

    # Add keyboard shortcut hints
    out += "\n\n#{Theme::INFO.render('q: quit')}"
    out
  end
end
