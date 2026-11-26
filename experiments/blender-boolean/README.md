# Blender Exact Boolean experiment

This is an isolated benchmark. It does not replace or modify the production CSG engine.

## 1. Capture the exact operands in CNC PRO 3D

1. Pull the latest `cam-native-rebuild` branch.
2. Open `index27.html` through the local HTTP server.
3. Open browser DevTools Console.
4. Run:
   ```js
   window.CNC_CAPTURE_BOOLEAN_INPUTS = true
   ```
5. Build the image relief normally and wait for the current CSG operation to finish.
6. In the console run:
   ```js
   window.exportCNCBooleanTestMeshes()
   ```
7. The browser downloads two files:
   - `cnc_boolean_target.stl` — exact normalized target operand used by CSG
   - `cnc_boolean_cutter.stl` — exact cutter operand, including its world transform

Keep both files in the repository root (or note their actual paths).

## 2. Run Blender Exact Difference

Open PowerShell in the repository folder and run:

```powershell
blender --version
blender -b --python experiments/blender-boolean/run_boolean.py -- --target cnc_boolean_target.stl --cutter cnc_boolean_cutter.stl --out cnc_blender_exact_result.stl --report cnc_blender_exact_report.json
```

If `blender` is not on PATH, replace `blender` with the full path to `blender.exe`.

The script:
- imports the two exported operands;
- records triangle counts and non-manifold/boundary edges;
- runs Boolean Difference with Blender's `EXACT` solver;
- records operation time and result topology;
- exports `cnc_blender_exact_result.stl` and a JSON report.

## 3. What to report back

Paste the complete PowerShell output and the contents of `cnc_blender_exact_report.json`.
Do not import the result into the production app yet. First we compare geometry quality and timings against the existing three-bvh-csg result.
