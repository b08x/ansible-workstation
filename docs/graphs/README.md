# Playbook graphs

Generated structure for each playbook in `playbooks/`, produced by
[ansible-playbook-grapher](https://github.com/haidaraM/ansible-playbook-grapher)
2.11.1 (ansible 2.18.2).

| Playbook | JSON | SVG |
| :--- | :--- | :--- |
| `site.yml` | `site.json` | `site.svg` |
| `base.yml` | `base.json` | — |
| `osbuild.yml` | `osbuild.json` | `osbuild.svg` |
| `dify-docker-ninjabot.yml` | `dify-docker-ninjabot.json` | `dify-docker-ninjabot.svg` |
| `langfuse-podman-tinybot.yml` | `langfuse-podman-tinybot.json` | `langfuse-podman-tinybot.svg` |

`base.yml` has no SVG on purpose: it is the system play of `site.yml` verbatim,
so its graph is a strict subgraph of `site.svg` and a second rendering would only
drift from the first. Read `base.json` if you need it as data.

## Regenerating

`--renderer` takes one value per run, so JSON and SVG are two invocations. The
tool writes output relative to the working directory, so pass `-o` explicitly
now that these live under `docs/graphs/`:

```bash
# SVG (graphviz is the default renderer)
ansible-playbook-grapher playbooks/site.yml -o docs/graphs/site

# JSON
ansible-playbook-grapher --renderer json playbooks/site.yml -o docs/graphs/site
```

`-o` takes a basename; the renderer appends the extension.

## Using these with archify

The JSON is the useful input. It carries the play/role/task hierarchy and edge
relationships as data — node ids, names, and the parent/child edges — which is
what a diagram needs, whereas the SVG is a finished graphviz layout that has
already thrown that structure away into absolute coordinates.

`site.json` is the one to reach for: it is the only graph covering both plays
(the privileged system play and the unprivileged user play), so it is the sole
artifact here that shows the full provisioning shape.

## Caveats for embedding

The SVGs carry a `<script>` block for grapher's hover and pan-zoom behaviour.
GitHub strips scripts when rendering SVG in Markdown, so an embedded graph is a
static image there and is interactive only when the file is opened directly in a
browser. `site.svg` is roughly 500 KB — link to it rather than inlining it on a
page that loads often.

The files are self-contained: no external `xlink:href` references, so they stay
valid if moved.
