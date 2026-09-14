require 'bubbletea'

class PlaybookModel
  include Bubbletea::Model
  attr_accessor :step, :roles, :cursor, :selected, :vars, :hostname,
                :yaml_output, :output_lines, :running, :rc, :paused

  def initialize
    @step = 1
    @roles = []
    @cursor = 0
    @selected = {}
    @vars = {}
    @hostname = "localhost"
    @yaml_output = ""
    @output_lines = []
    @running = false
    @rc = 0
    @paused = false
  end

  def init
    nil
  end
end
