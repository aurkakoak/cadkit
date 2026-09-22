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

The Linux installation lives in `~/.local/share/cadkit`. The first launch on
either platform creates an editable example project; subsequent launches keep
your edits.

## Open your own project

Your project directory must contain an importable Python module with a
`cadkit.Project` object. For a file named `project.py` containing `PROJECT`,
change into that directory and launch the app with `project:PROJECT`.

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
uv add "cadkit[desktop] @ git+https://github.com/aurkakoak/cadkit.git@v0.5.0"
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

Add dependencies to your project with `uv add`, then append this option to the
desktop launch command:

```sh
--python "$PWD/.venv/bin/python"
```

That interpreter must contain `cadkit[desktop]` and your project dependencies.
Use the same environment for CLI validation and desktop inspection.

| Problem | What to check |
| --- | --- |
| The app cannot import `project` | `--project-dir` points to the folder containing `project.py` |
| A dependency cannot be imported | Pass the project environment with `--python`; install the dependency there |
| `ocp_tessellate` is missing | Install CadKit with the `desktop` extra in the selected environment |
| `cadkit-desktop` is not found on Linux | Use its full `~/.local/bin/cadkit-desktop` path or add that directory to `PATH` |

See the [desktop reference](../reference/desktop.md) for launch options and
[Connect an agent](connect-an-agent.md) for sharing this session with an agent.
