# frozen_string_literal: true

require "bubbletea"

# Main application model for the Playbook Composer TUI.
#
# Implements the Bubbletea::Model interface for the Elm Architecture pattern.
# Manages state across multiple steps of playbook composition workflow.
#
# The workflow consists of 5 steps:
# 1. Choose a pre-defined scenario or start custom
# 2. Customize roles (if custom scenario selected)
# 3. Review variables
# 4. Review the generated playbook YAML
# 5. Execute the playbook with Ansible
#
# @example Creating and running the model
#   model = PlaybookModel.new
#   Bubbletea.run(model, alt_screen: true)
#
class PlaybookModel
  include Bubbletea::Model

  # Current step in the workflow (1-5)
  # @return [Integer] the current step number
  attr_accessor :step

  # Available roles scanned from the collection
  # @return [Array<Hash>] array of role hashes with :name, :path, :desc, :tasks_count
  attr_accessor :roles

  # Current cursor position in the selection list
  # @return [Integer] zero-based index of the current cursor position
  attr_accessor :cursor

  # Selection state for roles (role_name => boolean)
  # @return [Hash{String=>Boolean}] mapping of role names to selected state
  attr_accessor :selected

  # Variables scanned from inventory group_vars
  # @return [Hash{String=>Object}] flattened hash of all variables
  attr_accessor :vars

  # Target hostname for the playbook
  # @return [String] the hostname to use in the Ansible playbook
  attr_accessor :hostname

  # Generated YAML output for the playbook
  # @return [String] the complete YAML string of the generated playbook
  attr_accessor :yaml_output

  # Lines of output from Ansible execution
  # @return [Array<String>] array of output lines from the ansible-playbook run
  attr_accessor :output_lines

  # Whether Ansible is currently running
  # @return [Boolean] true if ansible-playbook is executing
  attr_accessor :running

  # Exit code from the last Ansible execution
  # @return [Integer] the exit status code (0 for success)
  attr_accessor :rc

  # Whether execution is paused
  # @return [Boolean] true if execution is paused
  attr_accessor :paused

  # Initialize a new PlaybookModel with default state.
  #
  # All state attributes are initialized to their default values.
  # The step starts at 1 (scenario selection), and all collections are empty.
  #
  # @return [PlaybookModel] a new model instance ready for the TUI workflow
  # @example Initial state
  #   model = PlaybookModel.new
  #   model.step # => 1
  #   model.roles # => []
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

  # Initialize the model for the Bubbletea lifecycle.
  #
  # This method is called by Bubbletea after the model is created.
  # Returns nil to indicate no initial command is needed.
  #
  # @return [nil] no initial command
  # @see Bubbletea::Model#init
  def init
    nil
  end
end
