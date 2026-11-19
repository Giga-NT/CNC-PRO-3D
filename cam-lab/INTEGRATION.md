# Vector CAM integration prototype

This branch adds a browser-facing adapter around the pinned OneManLabs CAM geometry pipeline. It does not embed or launch the upstream React application.

## Build

Run from the repository root in Windows PowerShell:

```powershell
.\cam-lab\setup-engine.ps1
```

The script checks out the pinned upstream revision, installs its locked dependencies, builds upstream CAM, then builds `cam-lab/dist/cnc-vector-cam.js`.

## What is connected

- `index27.html` loads the generated browser bundle.
- SVG import defaults to the CAM vector path; the UI selector retains a separate raster fallback.
- The bridge calls upstream `processSvg()` and exposes the semantic geometry at `window.CNCVectorGeometry`.
- Closed CAM loops are mapped into the existing editable polygon contour collection.
- Open paths and circles are retained separately and drawn as a 2D overlay; they are not silently closed or polygonized for cutting.
- CAM line and arc segments are preserved by the parser; arcs are sampled only for the current canvas display.
- The raster importer remains available as an explicit fallback.

## Current limitations

- Open paths and circles are display-only; they are not yet selectable/editable or connected to 3D cutting.
- Closed-loop display/editing uses the existing polygon editor, so arcs are currently tessellated for that editor.
- Region/island metadata is retained in the CAM result; only island loops are mapped to the editor's hole flags.
- No toolpath generation, stock-removal simulation, or machine-ready G-code integration is claimed by this milestone. Do not emit machine-ready G-code until machine, origin, tool and safety parameters are explicitly mapped and validated.

## Next integration milestone

Add native editable vector entities (including analytic arcs and circles), selection/movement/deletion, and project persistence. Then connect supported geometry to CAM toolpaths and stock simulation.

## API

`window.CNCVectorCAM.parseSvg(svgText)` returns counts plus the full parsed geometry. `window.CNCVectorGeometry` is set to the last imported SVG geometry by `index27.html`.

The bridge is a prototype; it has not yet been run in the user's local checkout after these changes.
