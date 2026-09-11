# Dev Container Configuration

Reference for `.devcontainer/podman/devcontainer.json` — what each `runArgs`
entry does, what the Podman docs say about it, and how the three dev container
variants in this repo differ.

## The three variants

| File | Runtime | `userns` | Security options | Capabilities added |
| --- | --- | --- | --- | --- |
| `.devcontainer/devcontainer.json` | Podman (rootless) | `keep-id` | `unmask=/sys/fs/cgroup` | none |
| `.devcontainer/podman/devcontainer.json` | Podman (rootless) | `keep-id` | `unmask=/sys/fs/cgroup` | none |
| `.devcontainer/docker/devcontainer.json` | Docker | — (Docker has no `--userns` flag here) | `seccomp=unconfined`, `label=disable`, `apparmor=unconfined` | `SYS_ADMIN`, `SYS_RESOURCE` |

The root and `podman/` variants are nearly identical. The `docker/` variant
carries more options because Docker does not support `--userns=keep-id` and
relies on capability adds and security-opt disables to achieve the same
nested-container functionality.

## runArgs explained

### `--device /dev/fuse`

Passes the FUSE device into the container. The `community-ansible-dev-tools`
image ships its own Podman so you can run molecule and nested containers from
inside the dev container. The inner Podman uses `fuse-overlayfs` as its
storage driver, which needs `/dev/fuse` to create the overlay filesystem for
nested container layers.

Without it, any `podman build` or `molecule` invocation inside the dev
container fails at the storage graph initialization step.

### `--security-opt unmask=/sys/fs/cgroup`

Makes the host's cgroup hierarchy visible inside the container at
`/sys/fs/cgroup`. Podman masks `/sys/fs/cgroup` by default to prevent the
container from reading or modifying host cgroup configuration. Nested
containers (podman-in-podman, molecule with systemd) need to read the cgroup
tree to place themselves in a cgroup, so the mask must be lifted.

### `--userns=keep-id`

Maps your host UID:GID to the same values inside a dedicated user namespace.
File ownership on bind-mounted workspace volumes stays consistent between
host and container, which prevents permission-denied errors when the VS Code
server process writes to the mounted workspace.

Podman offers several `--userns` modes (see `podman-run(1)`):

- **`host`** — the container runs in the caller's user namespace. Container
  UID 0 is literally your host UID. No user-namespace isolation; convenient
  and the weakest containment.
- **`keep-id`** — a dedicated user namespace is created. Your UID:GID is
  mapped to the same values *inside* that namespace. System calls in the
  container run inside the namespace, so it is more confined than `host`.
  This is the recommended default for rootless dev containers.
- Neither `host` nor `keep-id` is allowed for rootful containers.

Both Podman variants in this repo use `keep-id`. The Docker variant omits
`--userns` entirely because Docker does not support the same flag — it
relies on `updateRemoteUserUID: true` and `containerUser: root` for UID
mapping instead.

### `--cap-add=SYS_ADMIN`

Grants the `CAP_SYS_ADMIN` capability, which covers a broad set of
kernel operations including mount, namespace management, and cgroup
manipulation. Used in the Docker variant because nested Podman needs to
perform mounts (`mount(2)` calls) for overlay filesystems and does not
have `--userns=keep-id` to scope those operations into a user namespace.

The Podman variants do not add this capability — under `keep-id` with
`/dev/fuse` available, `fuse-overlayfs` handles the mount path inside the
user namespace without requiring `CAP_SYS_ADMIN`.

### `--cap-add=SYS_RESOURCE`

Grants `CAP_SYS_RESOURCE`, which allows the container to raise and override
various resource limits (cgroup memory limits, `RLIMIT_NOFILE`, etc.). The
Docker variant includes it so nested containers can adjust their own
cgroup limits when running under systemd or molecule.

### `--security-opt seccomp=unconfined`

Disables Podman's default seccomp filter. The default filter blocks
roughly 50 system calls that containers should never need. Disabling it
means the full syscall table is available to the container — useful when
nested containers invoke syscalls that the default profile blocks (for
example, some mount and namespace-manipulation calls used during image
build). Only present in the Docker variant.

### `--security-opt label=disable`

Tells Podman not to apply SELinux labels to the container's processes and
mounts. When SELinux is enforcing on the host, bind-mounted workspace
volumes can fail with permission errors because the container process
label does not match the file label. Disabling labeling avoids the
denial entirely. Only present in the Docker variant; the Podman variants
rely on `keep-id` and the root `devcontainer.json` comment notes that
`label=disable` can be added if SELinux denials on workspace volumes
appear.

### `--security-opt apparmor=unconfined`

Disables the AppArmor confinement profile. On hosts where AppArmor is
active, the default profile may block nested container operations. Only
present in the Docker variant.

### `--hostname=ansible-dev-container`

Sets the container's hostname. Cosmetic — useful for identifying the
container in prompts, logs, and `podman ps` output. Present in all three
variants.

## Non-runArgs settings

### `containerUser: root`

Sets the user the container process runs as. Under `--userns=keep-id`,
container root maps to your host UID, so file ownership on bind mounts
stays consistent. If `userns` were changed to `host`, container root would
be literally your host account — `containerUser: root` would then have
different semantics.

### `updateRemoteUserUID: true`

Tells the VS Code dev container infrastructure to update the remote
user's UID inside the container to match the host user's UID. This
matters once you leave `--userns=host` (where the mapping is implicit) and
use `keep-id` (where the VS Code server process needs its UID adjusted to
match the bind-mounted workspace files).

The `podman/` variant currently sets this to `false` because
`remoteUser: vscode` is used instead of `containerUser: root`, and the UID
mapping under `keep-id` already aligns the workspace ownership. The root
and Docker variants set it to `true` because they use `containerUser: root`.

## Why the nested container needs what it needs

The `community-ansible-dev-tools` image ships its own Podman so you can run
molecule and nested containers from inside the dev container. Nested
(inception) containers require:

- **`/dev/fuse`** — the inner Podman's `fuse-overlayfs` storage driver
  needs the FUSE device to create overlay filesystems.
- **cgroup visibility** — hence `unmask=/sys/fs/cgroup`. The inner
  container's runtime reads the cgroup tree to place itself.
- **Mount capability** — either `CAP_SYS_ADMIN` (Docker variant) or the
  user-namespace mount path available under `keep-id` with `/dev/fuse`
  (Podman variants).

## Notes on `userns=host` vs `keep-id`

- `host`: zero user-namespace isolation; container root is literally your
  host account. Convenient, weakest containment.
- `keep-id`: dedicated user namespace; your UID is mapped through but
  system calls in the container run inside it. Recommended default for
  rootless dev containers.
- Switching to `keep-id` means `containerUser: root` no longer maps to
  your host UID — verify file ownership of bind mounts after the switch,
  which is also why `updateRemoteUserUID: true` matters once you leave
  `host`.

Rootless containers "cannot gain more privileges than the user who
launched them" (`podman-exec(1)`), so capabilities like `NET_ADMIN` add
little real power in a rootless context but do widen the attack surface
if the definition is later run rootful.

`--privileged` disables dropped caps, device limits, label separation,
and seccomp all at once; the Podman docs warn it "should rarely be set".
None of the variants in this repo use `--privileged` — the Docker variant
achieves similar scope through individual security-opt disables and
capability adds, while the Podman variants avoid most of those entirely
by relying on `keep-id` and `/dev/fuse`.
