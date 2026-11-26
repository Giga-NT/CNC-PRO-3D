# Local surface relief experiment (no Boolean engine)

This is a standalone geometry test. It does **not** modify `index27.html` and does not change the production CSG path.

The test imports a stela STL and an image into Blender, subdivides only the front (+Z) surface, and displaces those front-surface vertices inward according to image brightness. The rest of the stone is not displaced. A soft fade at the image rectangle edge keeps the perimeter fixed. No Boolean operation is used.

## 1. Prepare inputs

1. In CNC PRO 3D, export the plain stela (without image relief) as STL, for example `test_stela.stl`.
2. Use the original image file you selected in the app, for example `relief.png`.
3. Put both files in the repository root (or note their full paths).

PNG with transparency is preferable. For JPG, the whole rectangular image is treated as the height map; background removal is not part of this first geometry test.

## 2. Run in PowerShell

From the repository root:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b --python experiments/local-surface-relief/run_test.py -- --target test_stela.stl --image relief.png --out local_surface_relief_test.stl --report local_surface_relief_report.json --depth-mm 3 --width-percent 70 --subdivisions 160
```

If Blender is installed elsewhere, change only the executable path.

Optional: add `--invert` to make dark pixels deeper instead of bright pixels.

## 3. What to inspect

- Open `local_surface_relief_test.stl` in Blender or the CNC PRO 3D viewer.
- Check whether the image is recognizable, whether the relief is confined to the image area, and whether the edge transition looks acceptable.
- Open `local_surface_relief_report.json`. The key fields are:
  - `front_subdivision_ms` and `total_ms` — performance
  - `vertices_displaced` — whether the height map affected the front
  - `after.triangles` — resulting mesh size
  - `after.non_manifold_edges`, `boundary_edges`, `wire_edges`
  - `closed_manifold` — should be true

This first pass intentionally prioritizes a quick geometry proof over reproducing all image-mask and ornament behavior from the app. It is not a production replacement yet.
