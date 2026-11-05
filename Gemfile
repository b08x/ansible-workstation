# frozen_string_literal: true

source "https://rubygems.org"

gem "ansible_module"
gem "ansible-vault"
gem "ansible-wrapper"
gem "bake"
gem "bcrypt_pbkdf"
gem "decode"
gem "dotenv"
gem "journald-logger"
gem "rake"
gem "rubydex"
gem "ratatui_ruby"
gem "ruby_tree_sitter"
gem "tree_sitter_language_pack"
gem "subspace"
gem "terrapin"
gem "yajl-ruby", require: "yajl"

# =============================================================================
# DEVELOPMENT & TEST DEPENDENCIES
# =============================================================================

group :development, :test do
  # Debugging
  gem "pry"
  gem "pry-byebug"

  # Testing
  gem "rack-test"
  gem "rspec"

  # Gherkin acceptance runner for features/*.feature (29 scenarios): the
  # implementer/verifier gates run `bundle exec cucumber`; before this pin the
  # gem was only installed globally, so the gates reported "not run: not in
  # the Gemfile bundle".
  gem "cucumber", "~> 12.0"

  # Code quality
  gem "rubocop"
  gem "rubocop-performance"
  gem "rubocop-rake"
  gem "rubocop-rspec"
  gem "rubocop-sequel"
  gem "rubocop-shopify"
  gem "rubocop-thread_safety"

  # Developer tools
  gem "ruby-lsp"
  gem "solargraph"
end



