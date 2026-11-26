# Kigumi Boolean experiment

This is an isolated test of the open-source Kigumi Boolean engine. It does not modify or replace the production three-bvh-csg engine in index27.html.

## License

Kigumi source is MIT-licensed. Its documented build requires CGAL's 2D Triangulations package, which is GPL or commercial, plus the CGAL geometry kernel (LGPL). This experiment is intended for an open-source/GPL-compatible test build. Review the licenses of the complete linked binary before redistributing it.

Upstream:
- https://github.com/unageek/kigumi
- https://github.com/CGAL/cgal

## 1. Get the test executable

The GitHub Actions workflow .github/workflows/kigumi-windows.yml builds the upstream Kigumi CLI for Windows x64.

After the workflow completes:
1. Open the repository's Actions tab.
2. Open Kigumi Windows build (experiment).
3. Open the latest successful run.
4. Download the kigumi-windows-x64 artifact.
5. Extract the ZIP and copy kigumi.exe into experiments/kigumi/bin/kigumi.exe.

The workflow is triggered by changes to this experiment folder or can be started manually from GitHub Actions.

## 2. Capture the exact CNC PRO operands

Use the existing Blender capture procedure from experiments/blender-boolean/README.md:
- cnc_boolean_target.stl
- cnc_boolean_cutter.stl

These must be the same two STL files used in the Blender test. Do not repair, simplify, or alter them.

## 3. Run Kigumi

Open PowerShell in the repository root and run:

~~~powershell
git pull origin cam-native-rebuild
powershell -ExecutionPolicy Bypass -File .\experiments\kigumi\run_kigumi_boolean.ps1
~~~

If Blender or Kigumi is installed elsewhere, pass explicit paths:

~~~powershell
powershell -ExecutionPolicy Bypass -File .\experiments\kigumi\run_kigumi_boolean.ps1 -Blender "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -Kigumi ".\experiments\kigumi\bin\kigumi.exe"
~~~

The script:
1. Imports the exact STL operands in Blender.
2. Writes world-space OBJ files without decimation, smoothing, welding, or face deletion.
3. Runs kigumi boolean with target minus cutter.
4. Runs kigumi check on the result.
5. Records elapsed Boolean time and diagnostic output.

## 4. Files to return

Send:
- the complete contents of cnc_kigumi_report.txt;
- the contents of cnc_kigumi_result.input-report.json;
- whether the result OBJ has the correct image relief when inspected in Blender.

Keep the output separate from the production app. A successful CLI exit or a clean topology report alone does not prove that the relief is geometrically correct.
