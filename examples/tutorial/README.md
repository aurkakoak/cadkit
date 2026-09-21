# Box-and-lid tutorial examples

These are complete snapshots of the [tutorial](../../docs/tutorials/index.md).
Each file is independent: copy one to `enclosure.py` in your own project to
start at that chapter. The tutorial uses CadKit 0.3.0 with Python 3.12.

| Section | Snapshot | Run after copying to `enclosure.py` |
| --- | --- | --- |
| 1. Make a box and a lid | `01_box.py` | `uv run python enclosure.py` |
| 2. Make a project | `02_project.py` | `uv run cadkit --project enclosure:PROJECT list` |
| 3. Inspect and export | `03_export.py` | `uv run python enclosure.py` |
| 4. Fasten the lid | `04_fasteners.py` | `uv run cadkit --project enclosure:PROJECT bom` |
| 5. Check a change | `05_checks.py` | `uv run cadkit --project enclosure:PROJECT validate-assembly` |
| 6. Work with an agent | `06_agent.py` | Open in the app; ask for `HEIGHT = 24`, then validate and export |

The box is 80 × 50 × 20 mm, with its rim at Z=0. The lid is 3 mm thick. The last
three snapshots add four matched mount sites, M3×8 screws and explicit insert
envelopes. They retain an `incomplete` mechanical status because a learning
model does not establish supplier fit, material strength or assembly sequence.
The normal examples have no confirmed failures. Changing `SCREW_LENGTH` from
8 to 4 in section 5 demonstrates a confirmed engagement failure.

From a CadKit source checkout, install the environment with
`uv sync --locked --extra desktop`, then run a snapshot directly:

```sh
uv run python examples/tutorial/01_box.py
PYTHONPATH=examples/tutorial uv run cadkit --project 05_checks:PROJECT validate-assembly
```

The test suite builds all six snapshots and verifies native exports, geometry,
hardware counts, blind-pocket floors, the deliberate failure and the agent's
height change:

```sh
uv run pytest tests/test_tutorial.py -q
```
