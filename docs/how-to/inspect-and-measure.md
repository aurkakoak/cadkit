# Inspect and measure an assembly

Start with your project [open in the desktop](install.md#open-your-own-project)
and a successful build. These steps use installed geometry. To inspect a
part's print orientation, export it from **Parts** instead.

## Find the object you need

Click an object in the viewport or assembly tree. Its inspector shows the
installed bounds and linked Part, where one is declared. Expand a subassembly
to select an individual instance rather than a whole branch.

Use the eye control to hide objects. The crosshair beside a tree row solos
that object or subassembly; click it again to restore the previous visibility.
**Show all** leaves solo mode and reveals the full model. Soloing a repeated
instance does not change the other instances' geometry.

The **Parts** list also includes manufacturing definitions with no installed
component, such as a calibration coupon. Selecting a Part and selecting an
installed instance answer different questions.

## Measure a gap

1. Select the first component, then Shift-click the second. You can also use
   the measurement A/B selectors.
2. Read the minimum-distance result and its measurement method.
3. For native geometry, inspect the closest-point markers and dimension line.

This measures whole components, not selected faces or edges. Native shapes are
measured in world millimetres by OpenCascade. Measurements involving a mesh
are labelled approximate and have no analytic closest-point markers.

A zero minimum distance can mean touching **or overlapping**. It does not
prove that a lid fits or that two parts are free of interference. Use
[assembly validation](export-and-check.md#review-the-installed-assembly) for
collision and declared-interface checks. Bounding-box centre distances and
axis deltas are separate values, not substitutes for the minimum gap.

## Review a connection

Open **Connections**, select a joint, interface or fastening, and inspect its
participants. For fastenings, review the hardware stack and quantities. Use
the hardware visibility modes to show all hardware, only the selected
connection, or none.

The assembly preview moves hardware along its declared insertion offsets.
Return the preview to zero before measuring: measurements use the installed
geometry, not the preview animation. Run assembly checks to inspect findings
and unverified coverage.

## Check a saved edit

After changing Python, wait for a successful rebuild. The app preserves the
camera, selection and visibility where component paths remain stable, and
recalculates active measurements. A failed rebuild keeps the previous model
visible; read the build status before trusting a new result.

Add a note from the selected item's inspector or tree row when discussing a
feature. Notes are shared with the agent, but last only for the current app
session. Record decisions you need to keep in source code or project docs.

For agent-controlled inspection and screenshots, see
[Connect an agent](connect-an-agent.md). Tool details are in the
[desktop reference](../reference/desktop.md).
