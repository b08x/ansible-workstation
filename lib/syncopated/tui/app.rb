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

module Syncopated
  module TUI
    class App
      # Entry point for the Playbook Composer TUI application.
      #
      # Initializes the model with scanned inventory data and starts
      # the Bubbletea event loop with alternate screen mode enabled.
      def self.start
        # Initialize the application model
        model = PlaybookModel.new

        # Scan the Ansible collection for available roles
        model.roles = Inventory.scan_roles

        # Scan the inventory for group variables
        model.vars = Inventory.scan_vars

        # Initialize role selection state
        model.roles.each do |r|
          model.selected[r[:name]] = false
        end

        # Start the Bubbletea application with alternate screen mode.
        Bubbletea.run(model, alt_screen: true)
      end
    end
  end
end
