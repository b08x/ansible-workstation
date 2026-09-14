#!/usr/bin/env ruby
# frozen_string_literal: true

require "bubbletea"
require_relative "theme"
require_relative "model"
require_relative "inventory"
require_relative "steps/scenarios"
require_relative "steps/roles"
require_relative "steps/variables"
require_relative "steps/review"
require_relative "steps/execute"
require_relative "update"
require_relative "view"

# Entry point for the Playbook Composer TUI application.
#
# Initializes the model with scanned inventory data and starts
# the Bubbletea event loop with alternate screen mode enabled.

# Initialize the application model
model = PlaybookModel.new

# Scan the Ansible collection for available roles
#
# @return [Array<Hash>] array of role info hashes
# @see Inventory.scan_roles
model.roles = Inventory.scan_roles

# Scan the inventory for group variables
#
# @return [Hash] hash of all variables from group_vars files
# @see Inventory.scan_vars
model.vars = Inventory.scan_vars

# Initialize role selection state
#
# All roles start unselected. The user will toggle them in step 2.
model.roles.each do |r|
  # By default, don't select anything
  model.selected[r[:name]] = false
end

# Start the Bubbletea application with alternate screen mode.
#
# Alternate screen mode provides a clean full-screen experience
# that doesn't scroll the terminal buffer.
#
# @param model [PlaybookModel] the initial application model
# @param alt_screen [Boolean] true to use alternate screen buffer
# @return [void] starts the event loop (blocks until exit)
# @see Bubbletea.run
Bubbletea.run(model, alt_screen: true)
