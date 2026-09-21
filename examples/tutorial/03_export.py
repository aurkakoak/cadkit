"""Chapter 3: export the two parts. Importing the file does not write files."""
import cadquery as cq

WIDTH = 80
DEPTH = 50
HEIGHT = 20
WALL = 2.4
LID_THICKNESS = 3


def box_body():
    # The rim is Z=0; the box extends down from it.
    outside = cq.Workplane("XY").rect(WIDTH, DEPTH).extrude(-HEIGHT)
    cavity = (cq.Workplane("XY").rect(WIDTH - 2 * WALL, DEPTH - 2 * WALL)
              .extrude(-(HEIGHT - WALL)))
    return outside.cut(cavity)


def lid_body():
    return cq.Workplane("XY").rect(WIDTH, DEPTH).extrude(LID_THICKNESS)


from cadkit import design as d

BOX = d.Part("box", box_body, manufacture=d.FDM("PETG"))
LID = d.Part("lid", lid_body, manufacture=d.FDM("PETG"))

DESIGN = d.Assembly("enclosure")
box = DESIGN.add("box", BOX, color=(0.32, 0.58, 0.72))
lid = DESIGN.add("lid", LID, color=(0.86, 0.70, 0.40), explode=(0, 0, 20))
DESIGN.fix(box)
DESIGN.fix(lid)
PROJECT = DESIGN.as_project()


# --8<-- [start:export]
if __name__ == "__main__":
    from cadkit.export import build

    build(PROJECT, PROJECT.select(["all"]), "build/enclosure")
# --8<-- [end:export]
