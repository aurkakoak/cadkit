# Slice a build

Use this guide to estimate print time and material for an exported part set.
You need CadKit, an installed PrusaSlicer, OrcaSlicer or Bambu Studio executable,
and actual printer, process and filament profiles. CadKit does not supply those
applications or choose a printer profile for you.

## Build the intended set

From your project directory:

```sh
uv run cadkit --project project:PROJECT build box lid --output-dir build/enclosure
```

Use your own Part names. The resulting `build/enclosure/manifest.json` defines
the exported set, quantities, material metadata and artifact hashes.

## Run the slicer from the CLI

For PrusaSlicer, supply a complete exported INI profile:

```sh
uv run cadkit-slice-build \
  --manifest build/enclosure/manifest.json \
  --slicer /absolute/path/to/prusa-slicer --slicer-kind prusa \
  --profile /absolute/path/to/printer.ini \
  --artifact-dir build/sliced \
  --output-json build/estimate.json --output-markdown build/estimate.md
```

For Bambu Studio, supply the three exported JSON profiles:

```sh
uv run cadkit-slice-build \
  --manifest build/enclosure/manifest.json \
  --slicer /absolute/path/to/BambuStudio --slicer-kind bambu \
  --machine-profile /absolute/path/to/machine.json \
  --process-profile /absolute/path/to/process.json \
  --filament-profile /absolute/path/to/filament.json \
  --artifact-dir build/sliced \
  --output-json build/estimate.json --output-markdown build/estimate.md
```

For OrcaSlicer, use its executable and `--slicer-kind orca`. Keep inherited or
included profile files available; CadKit resolves the exported profiles before
invoking the slicer. Executable and profile paths above are placeholders for
files on your machine.

The wrapper checks STL hashes against the build manifest. If you change an
STL after export, rebuild it through CadKit before slicing. Use `cadkit-slice`
instead when working with explicit STL paths and no CadKit build manifest.

## Choose quantities and materials

The manifest's quantities and groups are the defaults. `--group NAME` selects
one group; `--quantity-file` and `--group-file` supply explicit overrides. A
quantity override of zero omits an alternative.

Each run uses one filament profile. Slice PETG and TPU parts separately, even
when they belong to the same assembly. Quantities multiply per-part estimates;
the totals do not simulate arranging multiple parts on a packed plate.

## Use the desktop instead

Open **Print…** from a Part inspector, or the printer icon for a production
set. Select the parts and configure the slicer executable and profiles.

Choose **Open in slicer** to export print-oriented STLs for manual preparation.
Choose **Slice** to run a background job and see estimates. Review its logs,
retained files and generated G-code or 3MF in your slicer before printing.
No CadKit action submits a job to a printer.

Desktop artifacts remain under `build/desktop-slices/JOB_ID/`, including the
request, flattened profiles and reports. The live job list lasts for the app
session; the files survive it. A job retains the model revision and settings
it started with, so rebuild and reslice when an edit changes the intended part.

See the [CLI reference](../reference/cli.md) for options and
[Validation and evidence](../explanation/validation-and-evidence.md) for what
the retained reports do and do not establish.
