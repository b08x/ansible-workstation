# frozen_string_literal: true

require "nexo_ai"

module Syncopated
  class Agent < Nexo::Agent
    skills :syncopated
    sandbox :local
    permissions :auto
  end
end
