# Install CadKit

The desktop app includes Python and the CAD libraries. Launching without an
explicit project opens Projects, where the user can open a folder, create a starter
or copy the bracket example.

## macOS

On Apple Silicon or Intel Macs:

```sh
curl -fsSL https://aurkakoak.github.io/cadkit/install.sh | sh
```

Open `~/Applications/CadKit.app`. The installer selects your architecture,
checks the release checksum, and replaces an existing installation. You can
also download the matching `.dmg` from [GitHub Releases](https://github.com/aurkakoak/cadkit/releases/latest).

## Linux

On x64 or arm64 Linux:

```sh
curl -fsSL https://aurkakoak.github.io/cadkit/install.sh | sh
```

The installer selects the matching native `.tar.gz` release and verifies its
checksum. It installs the app in `~/.local/share/cadkit`, adds the
`~/.local/bin/cadkit-desktop` command and creates the app-menu entry
`~/.local/share/applications/cadkit.desktop`. Open CadKit from your app menu or
run `~/.local/bin/cadkit-desktop`.

## Open your own project

Use **Open…** in Projects and select the folder. CadKit discovers obvious
Python exports such as `project.py` containing `PROJECT` without importing the
project. Multiple exports appear in an entry-point chooser. Relative imports in
namespace packages are supported without adding `__init__.py` files.

**Settings** accepts an explicit folder, `module:attribute` reference
and Python interpreter. Omitted attributes mean `PROJECT`. Python remains the
sole project definition; do not add a manifest or run an initialization step
just to open an existing model. Opening the selected entry runs its builders.

**New** writes a minimal public-API starter into a new or empty folder.
**Examples → Create** copies the bracket example. The app stores recents and
previews in app data: pin entries, remove them without deleting source files, or
locate moved folders. The project menu can save the current view as its preview;
automatic captures from successful builds preserve that manual choice.

Explicit command-line launches still open their target directly. From the
directory containing `project.py`, launch the installed app on macOS:

```sh
"$HOME/Applications/CadKit.app/Contents/MacOS/CadKit" \
  --project-dir "$PWD" --project project:PROJECT
```

On Linux:

```sh
"$HOME/.local/bin/cadkit-desktop" \
  --project-dir "$PWD" --project project:PROJECT
```

The app uses its bundled Python by default. For projects with additional
Python dependencies, choose the interpreter in the picker's **Settings** (the
workbench opens it through **Project settings…**), or append
`--python /absolute/path/to/.venv/bin/python` to a direct launch.
That environment must have CadKit and its `desktop` extra installed.

## Python CLI and agent skill

For command-line modelling, install [uv](https://docs.astral.sh/uv/getting-started/installation/)
and create a project environment:

```sh
uv init --python 3.12 my-cad-project
cd my-cad-project
uv add cadkit-py
# Add your project.py, then:
uv run cadkit --project project:PROJECT build all
```

For a custom desktop environment: `uv add 'cadkit-py[desktop]'`.

Install the agent instructions from your project directory:

```sh
npx skills add aurkakoak/cadkit --skill cadkit
```

The skill installs documentation; the desktop app and Python CLI are installed
separately. See [working alongside the user](interaction.md) to connect the
running app to your agent.

## Local trial bundle

As an alternative to the published desktop app, a local trial bundle provides
a Python wheel and desktop source. Its desktop uses the consumer's Python
environment and requires a separate Node installation.

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
Python version, OS and architecture. CadQuery is pinned to 2.8.0. The local
trial desktop needs Node 24 and a graphical session. That source installation
path has been tested on Linux; validate other local trial environments before
using them. Blender, FFmpeg and slicers are separate applications, not
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

## Local trial desktop runtime

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
installed wheel. For a source development checkout, follow the uv setup below
and use its `desktop/` directory. This does not test the trial package's
installation boundary.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Cannot import consumer module | Install that checkout with its selected Python, or supply its `PYTHONPATH` |
| Cannot import `ocp_tessellate` | Install the wheel's `desktop` extra in the worker's Python |
| Electron executable missing | Run `npm run setup` after `npm ci` in the copied desktop directory |
| Qt/VTK/Chromium cannot open a display | Use a graphical session or an appropriate virtual display for tests |
| MCP says app is not running | Open the app with the same real project directory and project reference |
| Slicer cannot load profiles | Supply actual exported profiles and preserve inheritance/include files |

See [CadQuery adoption](migration.md), [API](api.md), [workflows](workflows.md), and the
desktop reference supplied with the release for the next steps.

## Development source selected by a consumer

Follow the consumer setup when it explicitly selects a CadKit source checkout
(e.g. `CADKIT_SOURCE`). Install that checkout and use its matching desktop
source. Its fastener catalogue is bundled in the Python package. A receipt for an
older trial is historical provenance, not a command to downgrade the active
source integration. Keep frozen trial bundles unchanged.

## Develop CadKit from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), clone this
repository, and run these commands from its root:

```sh
uv sync --locked --extra desktop
uv run --locked --extra desktop pytest tests -q
PYTHONPATH=examples uv run --locked cadkit --project bracket:PROJECT describe
uv build
```

uv selects Python 3.12 from `.python-version`, downloads it when needed, and
creates `.venv` with CadKit installed in editable mode. The committed `uv.lock`
records exact dependency versions. The pinned cq_warehouse fastener code and
catalogue data are bundled privately inside CadKit; their source revision and
licence are recorded in `src/cadkit/_vendor/cq_warehouse/README.md`.
Use `uv lock` after an intentional dependency change and commit the resulting
lockfile. The `--locked` flag makes CI fail when the lockfile needs updating.

The default `dev` dependency group supplies pytest. Documentation dependencies
are separate. Build the landing page and documentation without installing the
CAD runtime with:

```sh
uv run --locked --only-group docs python scripts/build_site.py
```

To preview the documentation locally, prepare its source files first, then
start MkDocs:

```sh
uv run --locked --only-group docs python scripts/build_site.py --prepare-only
uv run --locked --only-group docs mkdocs serve
```

To create a local trial bundle from this checkout:

```sh
uv run --locked python scripts/build_trial.py --label trial.1 --output /tmp/cadkit-trial.1
```

Consumer environments remain independent. If a consumer intentionally uses
this source checkout, install it into that consumer's selected interpreter with
`uv pip install --python /path/to/consumer/.venv/bin/python -e '/path/to/cadkit[desktop]'`.
