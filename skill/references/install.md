# Setup and runtime selection

Use this module for installation or an actual runtime change. Resolve existing
commands, Python, desktop and project reference from the consumer configuration
before installing anything. Keep the Python library and desktop on the selected
runtime; do not implicitly replace it with a registry version or adjacent checkout.

## Select the installation path

| Runtime | Setup |
| --- | --- |
| Packaged desktop | Uses bundled Python/CAD libraries. See [platform installation](https://aurkakoak.github.io/cadkit/docs/how-to/install/) for installers and platform paths. |
| Custom Python | Install `cadkit-py[desktop]` into the selected environment and pass its interpreter with `--python`. CLI-only use needs `cadkit-py`. The distribution is not named `cadkit`. |
| Development source | Follow the consumer's source override. In that framework checkout, `uv sync --locked --extra desktop`; in its `desktop/`, `npm ci` then `npm run setup`. Use the matching desktop and Python. |
| Supplied trial bundle | Use its `release.json` and `install.py`, as below. Keep the bundle frozen; use a separate directory for a new release. |

New standalone CLI projects can use `uv init --python 3.12`, then
`uv add cadkit-py`. Do not reinitialise an existing consumer. A custom desktop
environment can use `uv add 'cadkit-py[desktop]'`. Source/trial desktops need Node
matching their `package.json` engines and a graphical session. Blender, FFmpeg
and slicers are separate applications.

## Open the exact project

Python is the project definition; no additional manifest or initialisation is
needed to open it. The import reference is `module:attribute` (default attribute
`PROJECT`) and must resolve to `cadkit.Project`. For a `src/` layout, install the
consumer package into the selected interpreter, or set `PYTHONPATH` for **every**
command and launch. One shell command's environment does not configure a later app.

Example source launch with resolved paths:

```sh
npm --prefix /resolved/cadkit/desktop start -- \
  --project-dir /resolved/consumer --project my_cad.project:PROJECT \
  --python /resolved/consumer/.venv/bin/python
```

A packaged app accepts the same arguments on its executable. Each worktree has
its own project path and consumer installation. Settings in the app can select
the folder, entry point and worker Python. Skill installation supplies guidance;
MCP attaches separately to the running app through its plug configuration or
command helper. See [review](interaction.md) or [connection recovery](recovery.md).

## Supplied trial

Resolve `CADKIT_RELEASE` to the provided directory. An older skill receipt does
not override an explicitly configured development source. From the consumer root:

```sh
python3 "$CADKIT_RELEASE/install.py" verify
python3 "$CADKIT_RELEASE/install.py" python --python .venv/bin/python --desktop
python3 "$CADKIT_RELEASE/install.py" desktop --destination "$PWD/.cadkit/desktop"
npm --prefix .cadkit/desktop ci
npm --prefix .cadkit/desktop run setup
```

Create the virtual environment only if absent; install the consumer if packaged.
The installer does not overwrite an existing desktop directory. Its desktop
imports the installed wheel, without a source override. Record release hash and
resolved dependencies in the consumer setup; keep `.cadkit/` out of version control.
`install.py skill --project "$PWD"` installs the supplied skill when requested.

## Diagnose setup

Run `cadkit doctor` with the selected Python. Missing `ocp_tessellate` requires
the desktop extra in that interpreter; missing Electron requires `npm run setup`
in the configured desktop. Import failures usually require installing the exact
consumer checkout or fixing its `PYTHONPATH`. Display failures require a graphical
session (or a virtual display for tests). Use [recovery](recovery.md) to verify
the live connection after fixing the runtime.
