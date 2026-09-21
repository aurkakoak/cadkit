# 4. Fasten the lid

Add four screws that pass through the lid into heat-set inserts in the box.
The hole pattern, hardware and assembly relationship will come from one
`InsertMount` definition.

This step changes the box body, adds a shared mount recipe and connects the
parts. The excerpts below show each change. A complete file follows them so
you can check your edits or restart here.

## Make room for the inserts

Add these two constants after `LID_THICKNESS`:

```python
--8<-- "examples/tutorial/04_fasteners.py:sites"
```

The 2.4 mm walls are too thin for the example's 4 mm insert pockets. Inside
`box_body()`, replace `return outside.cut(cavity)` with:

```python
--8<-- "examples/tutorial/04_fasteners.py:pads"
```

This adds four 9 mm diameter pads at `(±34, ±19)`, extending 8 mm down from
the rim. Each pad overlaps the adjacent walls, making one connected solid.
The lid body stays unchanged.

## Define one shared mount

After the body builders, add the imports and a small insert builder:

```python
--8<-- "examples/tutorial/04_fasteners.py:insert"
```

Then define the shared mounting recipe:

```python
--8<-- "examples/tutorial/04_fasteners.py:mount"
```

`MOUNT` contains the four sites, an M3 × 8 mm screw, the insert definition,
a 3.4 mm clearance diameter and a 6.7 mm deep blind pocket.

The insert builder makes a simple annulus and labels it `representation="envelope"`.
Its outer diameter is 4.7 mm and its length is 5.7 mm. This lets us explore the
assembly without claiming that we have selected a manufacturer's insert.
The 4 mm pocket is an explicit modelling input; a real pocket must be chosen
for the purchased insert, material and printing process.

## Give each part its role

Replace the previous `BOX` and `LID` definitions with:

```python
--8<-- "examples/tutorial/04_fasteners.py:roles"
```

The box owns the receiving role, `MOUNT.insert_side()`. The lid owns the
through-hole role, `MOUNT.clearance_side(thickness=LID_THICKNESS)`. Building a
part now runs its CadQuery body builder and then applies its named features.
Both use the same `MOUNT`, so there is one source for the mating hole pattern.

## Connect the lid to the box

Replace the assembly block with:

```python
--8<-- "examples/tutorial/04_fasteners.py:connection"
```

Both role frames are at the rim, with +Z pointing out of the box into the lid.
This places pockets below the rim and clearance holes above it. The code now
fixes only the box. `DESIGN.connect(...)` aligns the two feature frames,
places the lid and creates the associated hardware. It replaces `fix(lid)`;
a connected instance should not also have a fixed placement.

Before running the model, copy the complete snapshot below into `enclosure.py`
or compare it with your edits. It includes the insert builder and all imports.

??? example "Complete enclosure with fasteners: enclosure.py"

    ```python
    --8<-- "examples/tutorial/04_fasteners.py"
    ```

[![The enclosure with four lid fasteners](../assets/tutorial/fasteners.png)](../assets/tutorial/fasteners.png)

After saving, show the lid and hardware in the app. You should see four screw
heads. Hide the lid to inspect the four receiving pads and inserts. The box
remains hollow between the pads.

## Count and inspect the hardware

```sh
uv run cadkit --project enclosure:PROJECT bom
uv run cadkit --project enclosure:PROJECT mechanics
uv run cadkit --project enclosure:PROJECT describe
```

The BOM has two rows: **four M3 × 8 screws** and **four M3 inserts**. The
mechanics output includes the `lid-mount` fastening and its four locations.
In the project description, the box's `design.operations` records insert
installation as a secondary manufacturing operation. Generating the pocket
geometry does not perform that operation.

The lid is 3 mm thick, so an 8 mm screw extends 5 mm into the receiver. That
exceeds the declared 3 mm minimum engagement and stays within the 6.7 mm
pocket. The next chapter will ask the mechanical validator to check this
relationship, then intentionally break it.

[Complete example](../../examples/tutorial/04_fasteners.py) ·
[← Inspect and export](03-inspect-and-export.md) ·
[Next: check a change →](05-check-and-change.md)
