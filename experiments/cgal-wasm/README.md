# CGAL WASM — isolated experiment

This folder is deliberately separate from `index27.html`. It does not import into CNC PRO 3D and does not change the production `three-bvh-csg` path.

## What this prototype tests

- CGAL 6.2.1
- `Exact_predicates_inexact_constructions_kernel` (EPICK)
- `Surface_mesh`
- `Polygon_mesh_processing::corefine_and_compute_difference()`
- WebAssembly execution inside a dedicated Web Worker
- Float32 position arrays and uint32 triangle indices across the JS/WASM boundary

The first browser test subtracts one overlapping cube from another. It is only a build/API smoke test, not yet a performance result for the stela.

## Build requirements

- Emscripten SDK with `emcmake` and `emmake` on PATH
- CMake 3.22+
- Git
- Boost headers 1.74+
- Internet access for the first configure (CGAL 6.2.1 is fetched from its official Git repository)

From this directory:

```powershell
emcmake cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 2
```

The generated `dist/cgal_boolean.js` and `dist/cgal_boolean.wasm` are loaded by `cgal-worker.js`.

## Run the browser test

Serve the repository over HTTP (do not open the HTML as file://):

```powershell
python -m http.server 8002
```

Open:

```
http://localhost:8002/experiments/cgal-wasm/test.html
```

Click **Вычесть тестовый куб**. The result should be a cube with a rectangular corner cut away. The page reports input validation time, Difference time, output vertex count and triangle count.

## Important limits of this first pass

- It currently tests two generated cubes only; it is not connected to the stela or image-relief UI.
- Mesh conversion welds exactly coincident coordinates and asks CGAL to orient the triangle soup. It rejects open or self-intersecting inputs rather than silently repairing them.
- Material groups and per-face material IDs are not preserved in the prototype output.
- EPICK uses exact predicates but inexact constructed coordinates. Output validation is included because this is a critical risk for dense relief cutters.
- A successful cube test does not prove that the real stela mesh is suitable or that CGAL is faster than three-bvh-csg.

No production code should be switched to this engine until the real stela test passes geometry checks and beats the existing 63–110 second baseline on a comparable run.
