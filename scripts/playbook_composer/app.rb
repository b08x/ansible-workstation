#!/usr/bin/env ruby

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

# Initialize state
model = PlaybookModel.new
model.roles = Inventory.scan_roles
model.vars = Inventory.scan_vars

# Set some defaults from the roles
model.roles.each do |r|
  # By default, don't select anything
  model.selected[r[:name]] = false
end

# Start the program
Bubbletea.run(model, alt_screen: true)
