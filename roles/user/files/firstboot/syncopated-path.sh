#!/bin/sh
# /etc/profile.d/syncopated-path.sh
# Deterministic PATH for Syncopated workstations.
# Baked into the image by the osbuild role; sourced by /etc/profile.
#
# Order (first match wins):
#   1. $HOME/.local/bin   — uv-managed tools, pipx, playwright, user pip installs
#   2. $HOME/.cargo/bin   — Rust cargo binaries
#   3. $HOME/go/bin       — Go binaries
#   4. $HOME/.bun/bin     — Bun global packages
#   5. /usr/local/bin     — Ansible-installed host binaries (bun, transcribe, etc.)
#   6. /usr/bin           — DNF/RPM system packages
#   7. /bin               — symlink to /usr/bin on Fedora (merged /usr)
#
# Explicitly EXCLUDED from PATH:
#   - /home/linuxbrew/.linuxbrew/bin and sbin  (Layer 2 yadm concern only)
#   - /opt/intel/oneapi/*                       (prepend via its own profile.d script)
#   - /usr/share/Modules/bin, /usr/lib64/ccache (environment-modules — not installed)
#   - ~/Tools/bin, ~/Workspace/bin              (ad-hoc — yadm Layer 2 concern)

PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/go/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

# Re-apply rbenv shims when /etc/profile.d/rbenv.sh ran earlier in collation order.
if [ -r /etc/profile.d/rbenv.sh ]; then
  # shellcheck source=/dev/null
  . /etc/profile.d/rbenv.sh
fi
