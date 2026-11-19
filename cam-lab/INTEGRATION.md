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
- On SVG import, the bridge calls upstream `processSvg()` and retains the resulting semantic geometry at `window.CNCVectorGeometry`.
- The geometry contains line/arc segments, circles, closed loops, regions and open paths, in millimetres.
- The current canvas/3D preview still uses the legacy raster-to-contour pipeline. This is deliberate: the existing editor and cutter expect closed polygon contours. Feeding open paths into that pipeline would corrupt the current workflow.

## Next integration milestone

Replace the legacy preview path in stages: draw vector open paths separately, map closed loops into the editor's editable geometry model, then connect selected vector entities to toolpath generation and stock simulation. Do not emit machine-ready G-code until machine, origin, tool and safety parameters are explicitly mapped and validated.

## API

`window.CNCVectorCAM.parseSvg(svgText)` returns counts plus the full parsed geometry. `window.CNCVectorGeometry` is set to the last imported SVG geometry by `index27.html`.

The bridge is a prototype; it has not yet been run in the user's local checkout after these changes.
