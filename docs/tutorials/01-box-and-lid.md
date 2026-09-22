# 1. Make a box and a lid

You will make two useful shapes before introducing CadKit's project model: an
open box and a flat lid that rests on its rim.

## Create a working directory

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you do
not already have it. Then run:

```sh
uv init --python 3.12 cadkit-box
cd cadkit-box
uv add "cadkit[desktop] @ git+https://github.com/aurkakoak/cadkit.git@v0.4.0"
```

This installs CadKit, CadQuery and the Python dependencies needed to open this
project in the desktop app. Keep the generated `pyproject.toml` and `uv.lock`;
they record the environment for your model. Run the remaining commands from
this directory.

## Write the shapes

Create `enclosure.py` with this complete example:

```python
--8<-- "examples/tutorial/01_box.py"
```

`Workplane("XY")` starts a sketch in the XY plane. `rect` makes a centred
rectangle, and `extrude` gives it height. Subtracting the smaller, shallower
solid with `cut` leaves four walls and a 2.4 mm floor.

We put the rim at **Z = 0**. The box extends down to Z = −20; the lid extends up
to Z = 3. Both shapes therefore use the same mating plane. Keeping that plane
fixed will make the later assembly easier to describe.

Each builder is a function that returns a CadQuery `Workplane`. Nothing is
built merely by importing the file. The `if __name__ == "__main__"` block runs
only when you execute it directly.

## Export the first result

```sh
uv run python enclosure.py
```

You should see:

```text
Wrote build/first-box/box.step and build/first-box/lid.step
```

These are native solid models. If you already use a STEP viewer, open them.
The box should measure 80 × 50 × 20 mm; the lid should measure 80 × 50 × 3 mm.
In the next chapter you will open both together in CadKit Desktop.

Try changing `HEIGHT` to `24`, run the command again, then change it back to
`20`. Only the box gets taller: its rim stays at Z = 0, and the lid is unchanged.
You now have a small parametric model, with dimensions collected at the top of
the file rather than spread across geometry operations.

[Complete example](../../examples/tutorial/01_box.py) ·
[Tutorial overview](index.md) · [Next: make a project →](02-project.md)
