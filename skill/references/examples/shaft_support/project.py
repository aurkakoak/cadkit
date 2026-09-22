"""CLI and desktop entry point for the shaft support example."""
import cadkit as ck

from .assemblies.bearing_unit import Dimensions, make_assembly, make_checks


def make_project(dimensions: Dimensions = Dimensions()) -> ck.Project:
    assembly = make_assembly(dimensions)
    return assembly.as_project(
        description="Two gravity-seated plain bearing supports and a hand-turned shaft.",
        parameters=dimensions.parameters(scope="bearing"),
        checks=make_checks(assembly),
    )


PROJECT = make_project()
