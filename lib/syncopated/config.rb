# frozen_string_literal: true

require "yaml"

module Syncopated
  module Config
    CONFIG_FILE = File.expand_path("~/.syncopated_llm.yml")

    class << self
      def load_llm_config
        if File.exist?(CONFIG_FILE)
          config = YAML.load_file(CONFIG_FILE) || {}
          ENV["NEXO_MODEL"] = config["model"] if config["model"]

          apply_ruby_llm_config(config)

          return true if config["model"]
        end
        false
      end

      def configure_llm(prompt, force: false)
        return if load_llm_config && !force

        prompt.puts "⚙️ \e[36mLLM Configuration Wizard\e[0m"
        provider = prompt.select("Select LLM Provider:") do |menu|
          menu.choice "Gemini", "gemini"
          menu.choice "OpenAI", "openai"
          menu.choice "Anthropic", "anthropic"
          menu.choice "OpenRouter", "openrouter"
          menu.choice "Ollama (Local)", "ollama"
        end

        config = { "provider" => provider }

        if provider == "ollama"
          if ENV["OLLAMA_API_URL"]
            prompt.puts "Detected OLLAMA_API_URL in environment."
            config["ollama_api_url"] = ENV["OLLAMA_API_URL"]
          else
            config["ollama_api_url"] = prompt.ask("Ollama URL:", default: "http://localhost:11434")
          end
        else
          api_key_env_var = "#{provider.upcase}_API_KEY"
          config_key = "#{provider}_api_key"

          if ENV[api_key_env_var]
            prompt.puts "Detected #{api_key_env_var} in environment."
            config[config_key] = ENV[api_key_env_var]
          else
            config[config_key] = prompt.mask("API Key (#{api_key_env_var}):")
          end
        end

        # Apply config so we can fetch models
        apply_ruby_llm_config(config)

        prompt.puts "Fetching available models..."
        begin
          RubyLLM.models.refresh!
        rescue => e
          prompt.error("Failed to fetch models: #{e.message}. Using offline registry.")
        end

        models = RubyLLM.models.by_provider(provider.to_sym).map(&:id).sort
        config["model"] = if models.any?
          prompt.select("Select Model:", models, filter: true, per_page: 15)
        else
          prompt.ask("Model:", default: default_model_for(provider))
        end

        config["temperature"] = prompt.ask("Temperature:", default: "0.7").to_f

        File.write(CONFIG_FILE, config.to_yaml)
        prompt.ok("Configuration saved to #{CONFIG_FILE}")

        load_llm_config
      end

      private

      def apply_ruby_llm_config(config)
        require "ruby_llm"
        RubyLLM.configure do |c|
          %w[gemini openai anthropic openrouter].each do |prov|
            key = "#{prov}_api_key"
            val = config[key] || ENV[key.upcase]
            c.send("#{key}=", val) if val
          end

          ollama_url = config["ollama_api_url"] || ENV["OLLAMA_API_URL"]
          c.ollama_api_url = ollama_url if ollama_url
        end
      end

      def default_model_for(provider)
        case provider
        when "gemini" then "gemini-2.5-pro"
        when "openai" then "gpt-4o"
        when "anthropic" then "claude-3-5-sonnet-20240620"
        when "openrouter" then "anthropic/claude-3.5-sonnet"
        when "ollama" then "llama3"
        end
      end
    end
  end
end
