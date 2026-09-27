# Review geometry and note placement

Use the live tool schemas for complete arguments. Read this module when a review
needs section conventions, coordinate annotations or lifecycle details.

## 2D geometry

Example `section_view` arguments, substituting live IDs and revision:

```json
{"revision":"…","ids":["/machine/clamp","/machine/shaft"],"mode":"section","plane":"XZ","offset":0,"tolerance":0.05,"show":true}
```

Planes use installed world coordinates in millimetres:

| Plane | Display axes | Section position |
| --- | --- | --- |
| XY | X/Y | Z = offset |
| XZ | X/Z | Y = offset |
| YZ | Y/Z | X = offset |

`section` intersects native shapes with the plane. `projection` projects all
native edges, including hidden ones; offset has no geometric effect. Restore
the installed pose first. Assembly IDs expand to components (maximum 100);
mesh-backed components are rejected. Curves are sampled at the requested
deflection (default 0.05 mm, range 0.001–1 mm), capped at 100,000 points.
These polylines are review geometry, not exact drawing exports or proof of fit.
Use native measurements and mechanical checks for engineering conclusions.

`show:true` opens the drawing with pan, zoom, participant highlighting and shared
notes. A missed cut reports **No intersection**. `show:false` returns labelled
polylines and bounds without changing the view. `get_state` returns a drawing
summary; screenshots include the visible drawing. `clear_section_view` preserves
notes and the 3D view. Successful rebuilds clear the drawing.

## Note placement

Prefer `target` for a note attached to a component or assembly's bounds. `offset`
is a pixel displacement from that anchor and overrides `from`; omitting both
lets the app place the card. For an arrow toward a known world location:

```json
{"revision":"…","id":"fit-arrow","text":"Check this interface","space":"world","from":[40,0,80],"point":[20,0,50]}
```

World coordinates track camera motion. Screen coordinates use `[x,y,0]`, with
x/y in 0–1 and origin at the viewport's top left. Target-only notes follow stable
IDs across rebuilds and disappear if the target is removed. Explicit `point`
or `from` coordinates and extra highlights clear on successful rebuild.

Notes support Markdown, up to 8,000 characters. Raw HTML is omitted and images
become alt text. Keep the finding in the first few lines: cards initially show
a four-line preview. An ID replaces the existing note with that ID; remove only
your own notes unless asked to clear others.
