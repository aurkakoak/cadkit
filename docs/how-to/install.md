# Install CadKit and open a project

The desktop app includes Python, CadQuery and CadKit. You need a separate Python
environment only for command-line work or a project with additional dependencies.
Published desktop builds support macOS and Linux on Intel/AMD 64-bit and ARM64.

## Install the desktop app

Run:

```sh
curl -fsSL https://aurkakoak.github.io/cadkit/install.sh | sh
```

The installer chooses the matching release and verifies its checksum before
replacing an existing installation. On macOS, open `~/Applications/CadKit.app`.
Current macOS builds are unsigned, so macOS may ask you to approve opening the
app. You can also download a DMG from
[GitHub Releases](https://github.com/aurkakoak/cadkit/releases/latest).

On Linux, open CadKit from the application menu, or run:

```sh
"$HOME/.local/bin/cadkit-desktop"
```

The Linux installation lives in `~/.local/share/cadkit`. Launching without a
project opens **Projects** on either platform.

## Open your own project

Choose **Open…** in Projects and select your project folder. CadKit looks
for Python entry points such as a `project.py` file containing `PROJECT`. Select
the entry you want if it finds several. Namespace packages work without
`__init__.py`; discovery chooses the containing import folder for relative imports.

For a custom layout, expand **Settings** and enter the folder and Python
import reference, such as `my_machine.project:PROJECT`. The referenced value must
be a compiled `cadkit.Project`. Python is the project definition; no CadKit
manifest or initialization command is needed. Discovery does not run the model;
opening it builds the geometry.

**New** writes a minimal starter in a new or empty folder.
**Examples → Create** copies the bracket example. Both ask where to save the
Python files and leave existing files untouched.

Recent projects appear with previews. Pin frequently used projects, remove an
entry without deleting its files, or choose **Locate folder** for a moved project.
The project menu's **Use current view as preview** saves your chosen view;
automatic previews from successful builds will not replace it. Return with the
**Home** button.

You can also open a project directly from a terminal. For `project.py` containing
`PROJECT`, change into its directory and launch with `project:PROJECT`.

On macOS:

```sh
"$HOME/Applications/CadKit.app/Contents/MacOS/CadKit" \
  --project-dir "$PWD" --project project:PROJECT
```

On Linux:

```sh
"$HOME/.local/bin/cadkit-desktop" \
  --project-dir "$PWD" --project project:PROJECT
```

The app watches Python files in this directory. Save a change and wait for a
successful rebuild before judging the result. A failed rebuild keeps the last
successful model visible.

If you have a CadQuery script without a `PROJECT` object, use
[Adopt an existing model](adopt-cadquery.md) first.

## Set up a Python project for the CLI

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then create
an environment:

```sh
uv init --python 3.12 my-cad-project
cd my-cad-project
uv add "cadkit[desktop] @ git+https://github.com/aurkakoak/cadkit.git@v0.5.2"
```

Add your `project.py`, then check that CadKit can load it:

```sh
uv run cadkit --project project:PROJECT describe
```

`--project` goes before the subcommand. Its value is a Python import reference,
not a file path: `package.model:PROJECT` imports `PROJECT` from `package.model`.
Run commands from the directory containing the module. A project using a
`src/` package layout should be installed into its environment with its own
packaging configuration.

The example pins a release from GitHub. Keep `pyproject.toml` and `uv.lock` in
version control so that collaborators use the same dependencies.

## Use additional Python dependencies in the desktop

Add dependencies to your project with `uv add`, then select that environment's
Python executable in the picker's **Settings → Python interpreter**. For an open
project, use **Project settings…** in its project menu. Leave the interpreter field
empty to use the app's default. For a direct launch, append:

```sh
--python "$PWD/.venv/bin/python"
```

That interpreter must contain `cadkit[desktop]` and your project dependencies.
Use the same environment for CLI validation and desktop inspection.

| Problem | What to check |
| --- | --- |
| The app cannot import `project` | Check the folder and entry point in Settings, or the `--project-dir` argument |
| A dependency cannot be imported | Choose the project's Python interpreter or pass `--python`; install the dependency there |
| `ocp_tessellate` is missing | Install CadKit with the `desktop` extra in the selected environment |
| `cadkit-desktop` is not found on Linux | Use its full `~/.local/bin/cadkit-desktop` path or add that directory to `PATH` |

See the [desktop reference](../reference/desktop.md) for launch options and
[Connect an agent](connect-an-agent.md) for sharing this session with an agent.
