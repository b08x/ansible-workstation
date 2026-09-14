def local_os_families
  return [] unless File.exist?("/etc/os-release")
  
  content = File.read("/etc/os-release")
  id = content.match(/^ID="?([^"\n]+)"?/)&.captures&.first&.downcase
  id_like = content.match(/^ID_LIKE="?([^"\n]+)"?/)&.captures&.first&.downcase
  
  families = [id].compact
  families += id_like.split(" ") if id_like
  
  ansible_map = {
    "redhat" => ["el", "redhat", "centos", "almalinux", "rocky", "rhel"],
    "fedora" => ["fedora", "el", "redhat"], # Some Fedora users might want EL roles? Maybe just fedora.
    "almalinux" => ["el", "redhat", "rhel"],
    "ubuntu" => ["debian", "ubuntu"],
    "pop" => ["debian", "ubuntu", "pop"]
  }
  
  expanded = families.dup
  families.each do |f|
    expanded += ansible_map[f] if ansible_map[f]
  end
  
  expanded.uniq.map(&:downcase)
end
puts local_os_families.inspect
