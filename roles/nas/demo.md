---
title: Setting Up NFS Server with Ansible
patat:
    wrap: false
    margins:
        left: 40
        right: 20
        top: 10
        bottom: 20
    incrementalLists: true
    theme:
      syntaxHighlighting:
        decVal: [rgb#b3122f]
      borders: [vividMagenta]
      definitionTerm: [vividRed]
      header: [vividGreen]
    images:
      backend: kitty
    pandocExtensions:
      - patat_extensions
      - autolink_bare_uris
      - emoji
---

# ...

---



---

Add parent folder and exports to `host_vars`

```yaml
share:
  nfs:
    parent: ""
    exports:
      - Library
```

---


Create NFS Root Directory:

```yaml
- name: Create exports folder
  file:
    path: /srv/exports
    state: directory
    owner: "{{ user.name }}"
    group: "{{ user.group }}"
    mode: "2775"
```

---

Create `nobody` User and Group:

```yaml
- block:
    - name: Ensure group nobody exists
      group:
        name: nobody
        gid: 65534
        non_unique: True
        system: True
```

Copy templates for `idmapd.conf` and `nfs.conf` from `etc/` to `/etc/`

```yaml
    - name: Install nfs configs
      template:
        src: "etc/{{ item }}.j2"
        dest: "/etc/{{ item }}"
        mode: "0644"
        backup: yes
      with_items:
        - idmapd.conf
        - nfs.conf
```

---

Enable NFS Services:

```yaml
    - name: Ensure nfs/rpc services are enabled and started
      service:
        name: "{{ item }}"
        state: restarted
        enabled: yes
      with_items:
        - nfs-server
        - nfs-mountd
        - nfs-idmapd
        - rpcbind
```


---

**Permit Traffic to `rpcbind`:**

   - For Archlinux and EndeavourOS, enable `firewalld` rules.
   - For MX and Debian, enable UFW rules.
   - Handle Errors in Check Mode

```yaml
- block:
    - name: Permit traffic to rpcbind
      firewalld:
        port: "{{ item }}"
        permanent: yes
        state: enabled
      with_items:
        - 111/tcp
        - 111/udp
        - 662/tcp
        - 662/udp
        - 892/tcp
        - 892/udp
        - 2049/tcp
        - 32769/udp
        - 32803/tcp
        - 40418/udp
      notify: reload firewalld

  when: ansible_os_family == 'Archlinux'

- block:
    - name: Permit tcp traffic to rpcbind
      community.general.ufw:
        rule: allow
        port: "{{ item }}"
        proto: tcp
      with_items:
        - "111"
        - "662"
        - "892"
        - "2049"
        - "32803"

    - name: Permit udp traffic to rpcbind
      community.general.ufw:
        rule: allow
        port: "{{ item }}"
        proto: udp
      with_items:
        - "111"
        - "662"
        - "892"
        - "32769"
        - "32803"

  when: ansible_distribution == 'MX' or ansible_distribution == 'Debian'

ignore_errors: "{{ ansible_check_mode }}"
```

---

Create Exported Folders:

```yaml
    - name: Ensure the exported folder already exists
      file:
        path: "{{ share.nfs.parent }}/{{ item }}"
        state: directory
        owner: "{{ user.name }}"
        group: "{{ user.group }}"
        mode: '2775'
      with_items:
        - "{{ share.nfs.exports }}"

    - name: Create exports folder
      file:
        path: /srv/exports/{{ item }}
        state: directory
        owner: "{{ user.name }}"
        group: "{{ user.group }}"
      with_items:
        - "{{ share.nfs.exports }}"
```


---

Add Entries to `/etc/fstab`:

```yaml
- name: Ensure required entries are made to hosts file. # Notes 1232
  lineinfile:
    path: /etc/fstab
    state: present
    line: "{{ share.nfs.parent }}/{{ item }} /srv/exports/{{ item }} none bind 0 0"
  with_items:
    - "{{ share.nfs.exports }}"
  register: fstab
```

Reload Systemd Daemon:

```yaml
- name: reload systemd
  systemd:
    daemon_reload: yes
  when: fstab.changed
```

Mount Exported Folders:

```yaml
- name: Mounted the binded folders
  shell: |
    mount /srv/exports/{{ item }}
  with_items:
    - "{{ share.nfs.exports }}"
```


---

Copy a template for `/etc/exports` file to specify exported folders and options

```yaml
- name: Set the exports
  template:
    src: etc/exports.j2
    dest: /etc/exports
    owner: root
    group: root
    mode: "0644"
    backup: yes
  register: exportsra
```

Reload Exports:

```yaml
- name: Reload exports
  shell: exportfs -rv
  when: exportsra.changed
```

---

# Conclusion

With this Ansible playbook, setting up an NFS server becomes a streamlined process.

---

# Questions?

Feel free to ask any questions you have about setting up an NFS server with Ansible.

<rwpannick@gmail.com>

---

# Thank You
