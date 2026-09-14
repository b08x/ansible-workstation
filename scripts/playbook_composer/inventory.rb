# frozen_string_literal: true

require "yaml"

# Inventory scanning utilities for the Playbook Composer.
#
# Provides methods to scan the local Ansible collection structure
# for available roles and variables. Used to populate the TUI
# with discoverable content from the filesystem.
#
# @example Scanning all inventory
#   roles = Inventory.scan_roles
#   vars = Inventory.scan_vars
#
module Inventory
  # Detect local OS families from /etc/os-release.
  #
  # Reads the OS release file and extracts ID and ID_LIKE fields,
  # then expands them using Ansible platform compatibility mappings.
  # This is used to filter roles that are compatible with the local system.
  #
  # @return [Array<String>] array of normalized OS family names
  # @raise [Errno::ENOENT] if /etc/os-release does not exist
  # @example On Fedora
  #   Inventory.local_os_families # => ["fedora", "el", "redhat"]
  def self.local_os_families
    return [] unless File.exist?("/etc/os-release")

    content = File.read("/etc/os-release")
    # Extract the primary OS ID (e.g., "fedora", "almalinux")
    id = content.match(/^ID="?([^"\n]+)"?/)&.captures&.first&.downcase
    # Extract ID_LIKE for compatibility mapping (e.g., "rhel fedora")
    id_like = content.match(/^ID_LIKE="?([^"\n]+)"?/)&.captures&.first&.downcase

    families = [id].compact
    families += id_like.split if id_like

    # Ansible platform name mappings for role compatibility checking.
    # Maps canonical names to their compatible platform variants.
    #
    # @type [Hash{String=>Array<String>}] platform name to compatible variants
    ansible_map = {
      "redhat" => %w[el redhat centos almalinux rocky rhel],
      "fedora" => %w[fedora el redhat],
      "almalinux" => %w[almalinux el redhat rhel],
      "centos" => %w[centos el redhat rhel],
      "ubuntu" => %w[ubuntu debian pop],
      "debian" => %w[debian ubuntu],
      "pop" => %w[pop ubuntu debian],
    }

    expanded = families.dup
    families.each do |f|
      expanded += ansible_map[f] if ansible_map[f]
    end

    expanded.uniq.map(&:downcase)
  end

  # Scan available Ansible roles from the collection structure.
  #
  # Walks the collections/ansible_collections/b08x/*/roles/ directory tree
  # and extracts role metadata from meta/main.yml files.
  # Filters roles to only those compatible with the local OS.
  #
  # @return [Array<Hash{Symbol=>String,Integer}>] sorted array of role info hashes
  # @return [Hash] each hash contains :name, :path, :desc, :tasks_count
  # @example
  #   roles = Inventory.scan_roles
  #   roles.first # => { name: "base", path: ".../base/", desc: "Base OS config", tasks_count: 5 }
  def self.scan_roles
    roles = []
    # Find all role directories in the b08x collections
    Dir.glob("collections/ansible_collections/b08x/*/roles/*/").each do |dir|
      # Extract the role name from the directory path
      name = dir.split("/")[-1]
      meta_file = File.join(dir, "meta", "main.yml")
      tasks_file = File.join(dir, "tasks", "main.yml")

      desc = "No description"
      supported = true

      # Try to extract description from role metadata
      if File.exist?(meta_file)
        begin
          meta = YAML.load_file(meta_file)
          # Extract description from galaxy_info in metadata
          desc = meta.dig("galaxy_info", "description") || desc

          # Check platform compatibility if role specifies platforms
          platforms = meta.dig("galaxy_info", "platforms")
          if platforms.is_a?(Array)
            # Get local OS families for compatibility check
            local_os = local_os_families
            # Extract platform names from role metadata
            role_os = platforms.map { |p| p["name"].to_s.downcase }

            # Role is only supported if its platforms overlap with local OS
            supported = false unless local_os.intersect?(role_os)
          end
        rescue StandardError
          # Silently handle any YAML parsing or structure errors
        end
      end

      next unless supported

      # Count tasks in the role's main tasks file
      tasks_count = 0
      if File.exist?(tasks_file)
        begin
          tasks = YAML.load_file(tasks_file)
          tasks_count = tasks.is_a?(Array) ? tasks.length : 0
        rescue StandardError
          # Silently handle any YAML parsing errors
        end
      end

      # Add role info to results
      roles << { name:, path: dir, desc:, tasks_count: }
    end
    # Sort roles alphabetically by name for consistent display
    roles.sort_by { |r| r[:name] }
  end

  # Scan variables from Ansible inventory group_vars files.
  #
  # Reads all YAML files from inventory/group_vars/ directory
  # and merges them into a single hash. Later files override
  # earlier ones if there are key conflicts.
  #
  # @return [Hash{String=>Object}] merged hash of all group variables
  # @raise [Errno::ENOENT] if inventory/group_vars directory does not exist
  # @example
  #   vars = Inventory.scan_vars
  #   vars["some_setting"] # => "value from group_vars"
  def self.scan_vars
    vars = {}
    # Find all group_vars YAML files
    Dir.glob("inventory/group_vars/*.yml").each do |file|
      data = YAML.load_file(file)
      # Merge hash data into the result (later files override earlier)
      vars.merge!(data) if data.is_a?(Hash)
    rescue StandardError
      # Silently handle any YAML parsing errors
    end
    vars
  end
end
