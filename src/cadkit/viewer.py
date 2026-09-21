"""CadQuery's CQ viewer and the show_object convention used by CQ-editor."""

import cadquery as cq
from .geometry import Mesh, shape


def show_components(
    components, *, show_object=None, exploded=False, screenshot=None, interact=True
):
    """Display installed Components in the CQ viewer or a CQ-editor callback.

    Args:
        components (list): Installed Components.
        show_object (Callable | None): Optional CQ-editor-compatible callback.
            It cannot display explicit Meshes; those are reported separately.
        exploded (bool): Apply full Component explosion translations.
        screenshot (str | None): Optional output image for the standalone viewer.
        interact (bool): Keep the standalone viewer interactive.

    Native geometry uses CadQuery's viewer; Meshes are shown as VTK actors.
    This function does not start CadKit Desktop or expose its MCP bridge.
    """
    assembly = cq.Assembly(name="CAD project")
    actors = []
    for c in components:
        model = c.placed(1 if exploded else 0)
        if isinstance(model, Mesh):
            from vtkmodules.vtkIOGeometry import vtkSTLReader
            from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory(prefix="cadkit-view-") as temp:
                path = Path(temp) / "component.stl"
                model.triangles().export(path)
                reader = vtkSTLReader()
                reader.SetFileName(str(path))
                reader.Update()
                mapper = vtkPolyDataMapper()
                mapper.SetInputData(reader.GetOutput())
                actor = vtkActor()
                actor.SetMapper(mapper)
                actor.GetProperty().SetColor(*c.color)
                actors.append(actor)
            if show_object:
                # CQ-editor cannot show triangle meshes through show_object.
                # Preserve the explicit distinction instead of inventing a solid.
                print(f"{c.name}: mesh component available in cadkit preview / Blender")
        elif show_object:
            show_object(model, name=f"{c.group}/{c.name}", options={"color": c.color})
        else:
            assembly.add(model, name=c.name, color=cq.Color(*c.color))
    if not show_object:
        from cadquery.vis import show

        show(
            assembly,
            *actors,
            title="CadKit · CQ viewer",
            screenshot=screenshot,
            interact=interact,
            width=1200,
            height=900,
            gradient=True,
            edges=False,
        )
