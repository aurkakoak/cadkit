# Export and utilities

The project-aware `build()` entry point runs the mechanical export gate when
a project declares joints, interfaces or fastenings. Lower-level exporters
are available for callers that deliberately own their own validation flow.
See [file contracts](contracts.md) for generated filenames and fields.

## Fabrication

::: cadkit.export.build
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.export.export_part
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.export.inspect_model
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.export.validate_part
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.export.export_stl
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.export.run_checks
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

## Installed assemblies and render assets

::: cadkit.export.export_assembly
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.export.export_render_assets
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

## Preflight

Scoping a print set preserves the complete installed assembly as context.
An explicit override records a decision to export with findings; it does not
change a failed report into evidence that the model is correct.

::: cadkit.preflight.scoped_report
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

::: cadkit.preflight.reviewed_report
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

## CQ viewer

::: cadkit.viewer.show_components
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3

## Geometry builder cache

::: cadkit.cache.memoize_shape
    options:
      show_root_heading: true
      show_root_full_path: false
      heading_level: 3
