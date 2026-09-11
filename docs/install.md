# Install CadKit in a consumer project

CadKit is a Python library and CLI. Its optional Electron desktop is a separate
runtime using the consumer's Python environment. Installing the skill only
installs documentation; it does not install either runtime.

## Local trial bundle

Set `CADKIT_RELEASE` to the supplied extracted release folder, containing
`release.json` and `install.py`. If a local skill was installed by that script,
its `release.json` records the release path and manifest hash. No registry login
is needed. Keep the bundle unchanged; use a new directory for each release.

From the consumer project root:

```sh
export CADKIT_RELEASE=/absolute/path/to/cadkit-trial
python3 "$CADKIT_RELEASE/install.py" verify
python3 "$CADKIT_RELEASE/install.py" skill --project "$PWD"
python3 -m venv .venv  # skip if the project already has a suitable environment
python3 "$CADKIT_RELEASE/install.py" python --python .venv/bin/python --desktop
.venv/bin/python -m pip install -e .  # install the consumer, if it is a package
.venv/bin/cadkit doctor
```

The installer copies a self-contained skill to `.agents/skills/cadkit`. It will
not overwrite an existing skill or desktop directory. The equivalent skill-only
command is `npx skills add "$CADKIT_RELEASE/skills" --skill cadkit --agent codex
--copy`; with that route, keep the release path from the installation command.
Start a fresh agent task after installation, or explicitly read the installed
`SKILL.md` if your host has not refreshed skill discovery.

The Python command installs the bundle's wheel with the optional `desktop`
extra, using the exact interpreter supplied. Omit `--desktop` for CLI-only use.
Record the wheel version and release manifest hash in the consumer's setup
instructions. This local trial is not published to PyPI: do not substitute an
unrelated package named `cadkit` from a registry. The framework wheel and npm
lockfile are frozen; Python's transitive dependencies resolve at installation.
Record `pip freeze` alongside validation results to reproduce that environment.

Python 3.11+ is declared; binary CadQuery/OCP availability still depends on
Python version, OS and architecture. CadQuery is pinned to 2.8.0. Desktop needs
Node 22.12+ and a graphical session. Linux is tested; other desktop platforms
need validation. Blender, FFmpeg and slicers are separate applications, not
Python extras. Printer profiles remain local consumer inputs.

## Everyday use

The installed `$cadkit` skill supports ongoing modelling and working with the
live app. In a fresh task in the consumer checkout, try:

> Use $cadkit. Inspect the part I have selected in the open app.

See [working alongside the user](interaction.md) for selection, measurements,
annotations and the edit/rebuild loop. The skill supplies instructions; live
tools come from a configured MCP connection or a consumer command helper.

## Importable project

Commands take `--project package.module:PROJECT` before the subcommand. That
attribute must be an instance of `cadkit.Project`. For a `src/` layout, install
the consumer with its own packaging metadata. Alternatively set `PYTHONPATH`
to its source directory for every command and desktop launch. A shell setting
for one command does not persist into a later desktop process.

```sh
.venv/bin/cadkit --project my_cad.project:PROJECT describe
.venv/bin/cadkit --project my_cad.project:PROJECT build all
```

For a standalone example, copy `examples/bracket.py` from the release into an
empty working directory and use `--project bracket:PROJECT` with that directory
on `PYTHONPATH`. No sibling CAD checkout is needed.

## Desktop runtime

Copy the desktop sources into a writable consumer-local runtime, then install
its locked npm dependencies. Keep `.cadkit/` out of version control; keep the
skill and consumer setup commands in version control.

```sh
python3 "$CADKIT_RELEASE/install.py" desktop --destination "$PWD/.cadkit/desktop"
npm --prefix .cadkit/desktop ci
npm --prefix .cadkit/desktop run setup
npm --prefix .cadkit/desktop start -- \
  --project-dir "$PWD" --project my_cad.project:PROJECT \
  --python "$PWD/.venv/bin/python"
```

Each checkout/worktree needs its own consumer installation and runtime paths.
The desktop copies contain no Python source override; the worker imports the
installed wheel. A source development checkout can instead use
`pip install -e /path/to/cadkit[desktop]` and its `desktop/` directory, but this
does not test the trial package's installation boundary.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Cannot import consumer module | Install that checkout with its selected Python, or supply its `PYTHONPATH` |
| Cannot import `ocp_tessellate` | Install the wheel's `desktop` extra in the worker's Python |
| Electron executable missing | Run `npm run setup` after `npm ci` in the copied desktop directory |
| Qt/VTK/Chromium cannot open a display | Use a graphical session or an appropriate virtual display for tests |
| MCP says app is not running | Open the app with the same real project directory and project reference |
| Slicer cannot load profiles | Supply actual exported profiles and preserve inheritance/include files |

See [migration](migration.md), [API](api.md), [workflows](workflows.md), and the
desktop reference supplied with the release for the next steps.
