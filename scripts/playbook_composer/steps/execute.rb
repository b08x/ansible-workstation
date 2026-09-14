require 'open3'
require 'bubbles'

class ExecDoneMsg < Bubbletea::Message
  attr_accessor :output, :rc
  def initialize(output, rc)
    @output = output
    @rc = rc
  end
end

class PlaybookModel
  def start_execute_cmd
    @spinner ||= Bubbles::Spinner.new(spinner: Bubbles::Spinners::DOT)
    
    exec_task = -> {
      File.write("dynamic_run.yml", self.yaml_output)
      stdout_str, stderr_str, status = Open3.capture3("ansible-playbook dynamic_run.yml")
      ExecDoneMsg.new(stdout_str + "\n" + stderr_str, status.exitstatus)
    }
    
    Bubbletea.batch(exec_task, @spinner.tick)
  end

  def update_execute(msg)
    @spinner ||= Bubbles::Spinner.new(spinner: Bubbles::Spinners::DOT)
    
    if msg.is_a?(ExecDoneMsg)
      self.running = false
      self.output_lines = msg.output.split("\n")
      self.rc = msg.rc
      return [self, nil]
    end
    
    if self.running
      @spinner, cmd = @spinner.update(msg)
      return [self, cmd]
    end
    
    [self, nil]
  end

  def view_execute
    out = Theme::HEADER.render("Step 5: Execute Playbook") + "\n\n"
    
    if self.running
      @spinner ||= Bubbles::Spinner.new(spinner: Bubbles::Spinners::DOT)
      out += "#{@spinner.view} Running ansible-playbook... Please wait.\n"
    else
      out += "Execution finished with code #{self.rc}\n\n"
      tail = self.output_lines.last(15).join("\n")
      out += tail
    end
    
    out += "\n\n" + Theme::INFO.render("q: quit")
    out
  end
end
