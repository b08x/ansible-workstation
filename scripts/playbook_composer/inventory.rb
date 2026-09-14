require 'yaml'

module Inventory
  def self.local_os_families
    return [] unless File.exist?("/etc/os-release")
    
    content = File.read("/etc/os-release")
    id = content.match(/^ID="?([^"\n]+)"?/)&.captures&.first&.downcase
    id_like = content.match(/^ID_LIKE="?([^"\n]+)"?/)&.captures&.first&.downcase
    
    families = [id].compact
    families += id_like.split(" ") if id_like
    
    ansible_map = {
      "redhat" => ["el", "redhat", "centos", "almalinux", "rocky", "rhel"],
      "fedora" => ["fedora", "el", "redhat"],
      "almalinux" => ["almalinux", "el", "redhat", "rhel"],
      "centos" => ["centos", "el", "redhat", "rhel"],
      "ubuntu" => ["ubuntu", "debian", "pop"],
      "debian" => ["debian", "ubuntu"],
      "pop" => ["pop", "ubuntu", "debian"]
    }
    
    expanded = families.dup
    families.each do |f|
      expanded += ansible_map[f] if ansible_map[f]
    end
    
    expanded.uniq.map(&:downcase)
  end

  def self.scan_roles
    roles = []
    Dir.glob("collections/ansible_collections/b08x/*/roles/*/").each do |dir|
      name = dir.split('/')[-1]
      meta_file = File.join(dir, "meta", "main.yml")
      tasks_file = File.join(dir, "tasks", "main.yml")
      
      desc = "No description"
      supported = true
      
      if File.exist?(meta_file)
        begin
          meta = YAML.load_file(meta_file)
          desc = meta.dig("galaxy_info", "description") || desc
          
          platforms = meta.dig("galaxy_info", "platforms")
          if platforms && platforms.is_a?(Array)
            # Check if any platform matches our local OS
            local_os = local_os_families
            role_os = platforms.map { |p| p["name"].to_s.downcase }
            
            # If role specifies platforms, it must overlap with local OS
            supported = false if (local_os & role_os).empty?
          end
        rescue
        end
      end
      
      next unless supported
      
      tasks_count = 0
      if File.exist?(tasks_file)
        begin
          tasks = YAML.load_file(tasks_file)
          tasks_count = tasks.is_a?(Array) ? tasks.length : 0
        rescue
        end
      end
      
      roles << { name: name, path: dir, desc: desc, tasks_count: tasks_count }
    end
    roles.sort_by { |r| r[:name] }
  end

  def self.scan_vars
    vars = {}
    Dir.glob("inventory/group_vars/*.yml").each do |file|
      begin
        data = YAML.load_file(file)
        vars.merge!(data) if data.is_a?(Hash)
      rescue
      end
    end
    vars
  end
end
