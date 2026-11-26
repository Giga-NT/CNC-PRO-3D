import argparse
import json
import math
import os
import sys
import time

import bpy
import bmesh
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description="Local front-surface heightfield relief test")
    p.add_argument("--target", required=True, help="Closed stela STL exported from CNC PRO 3D")
    p.add_argument("--image", required=True, help="Original PNG/JPG/WebP image")
    p.add_argument("--out", default="local_surface_relief_test.stl")
    p.add_argument("--report", default="local_surface_relief_report.json")
    p.add_argument("--depth-mm", type=float, default=3.0)
    p.add_argument("--width-percent", type=float, default=70.0)
    p.add_argument("--subdivisions", type=int, default=160,
                   help="Subdivision cuts on front-face edges; higher gives finer relief")
    p.add_argument("--invert", action="store_true", help="Make dark pixels deeper instead of bright pixels")
    p.add_argument("--feather-percent", type=float, default=4.0,
                   help="Soft zero-displacement border as percent of the shorter image dimension")
    return p.parse_args(argv)


def import_stl(path):
    before = set(bpy.data.objects)
    if hasattr(bpy.ops.wm, "stl_import"):
        bpy.ops.wm.stl_import(filepath=os.path.abspath(path))
    else:
        bpy.ops.import_mesh.stl(filepath=os.path.abspath(path))
    created = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if not created:
        raise RuntimeError("STL import created no mesh object")
    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    if len(created) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = "CNC_Local_Surface_Relief"
    return obj


def stats(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    result = {
        "vertices": len(bm.verts),
        "edges": len(bm.edges),
        "faces": len(bm.faces),
        "triangles": sum(len(f.verts) - 2 for f in bm.faces),
        "non_manifold_edges": sum(not e.is_manifold for e in bm.edges),
        "boundary_edges": sum(e.is_boundary for e in bm.edges),
        "wire_edges": sum(e.is_wire for e in bm.edges),
        "signed_volume_m3": round(float(bm.calc_volume(signed=True)), 9),
    }
    bm.free()
    return result


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def main():
    args = parse_args()
    if not os.path.isfile(args.target):
        raise FileNotFoundError(args.target)
    if not os.path.isfile(args.image):
        raise FileNotFoundError(args.image)
    if args.depth_mm <= 0 or args.width_percent <= 0 or args.width_percent > 100:
        raise ValueError("Depth must be positive; width-percent must be in (0, 100]")
    if args.subdivisions < 4:
        raise ValueError("Use at least 4 subdivisions")

    started = time.perf_counter()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    obj = import_stl(args.target)
    before = stats(obj)

    # STL coordinates are imported in world-aligned local space by Blender's STL importer.
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.normal_update()

    zmax = max(v.co.z for v in bm.verts)
    zmin = min(v.co.z for v in bm.verts)
    x_min = min(v.co.x for v in bm.verts)
    x_max = max(v.co.x for v in bm.verts)
    y_min = min(v.co.y for v in bm.verts)
    y_max = max(v.co.y for v in bm.verts)
    eps = max(1e-6, (zmax - zmin) * 1e-4)

    front_faces = [f for f in bm.faces if f.normal.z > 0.90 and abs(f.calc_center_median().z - zmax) <= eps]
    if not front_faces:
        bm.free()
        raise RuntimeError("Could not identify the front (+Z) planar faces. Check STL orientation.")
    front_edges = list({e for f in front_faces for e in f.edges})
    if not front_edges:
        bm.free()
        raise RuntimeError("Front surface has no edges")

    # Subdivide only edges belonging to the front face. Shared perimeter edges
    # are split consistently in adjacent side faces, preserving connectivity.
    subdiv_started = time.perf_counter()
    bmesh.ops.subdivide_edges(
        bm, edges=front_edges, cuts=args.subdivisions,
        use_grid_fill=True, smooth=0.0
    )
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    subdiv_ms = (time.perf_counter() - subdiv_started) * 1000.0

    image = bpy.data.images.load(os.path.abspath(args.image), check_existing=False)
    image_size = [int(image.size[0]), int(image.size[1])]
    if image_size[0] < 2 or image_size[1] < 2:
        bm.free()
        raise RuntimeError("Image is too small")
    pixels = list(image.pixels[:])
    iw, ih = image_size
    aspect = iw / ih
    stone_w = x_max - x_min
    stone_h = y_max - y_min
    relief_w = stone_w * args.width_percent / 100.0
    relief_h = relief_w / aspect
    if relief_h > stone_h * 0.68:
        relief_h = stone_h * 0.68
        relief_w = relief_h * aspect
    cx = (x_min + x_max) * 0.5
    cy = (y_min + y_max) * 0.5
    left, right = cx - relief_w * 0.5, cx + relief_w * 0.5
    bottom, top = cy - relief_h * 0.5, cy + relief_h * 0.5
    feather = max(1e-6, min(relief_w, relief_h) * args.feather_percent / 100.0)
    depth = args.depth_mm / 1000.0

    def sample(u, v):
        # Blender image pixels are bottom-left origin.
        px = max(0, min(iw - 1, int(round(u * (iw - 1)))))
        py = max(0, min(ih - 1, int(round(v * (ih - 1)))))
        k = (py * iw + px) * 4
        r, g, b, a = pixels[k:k + 4]
        gray = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return (1.0 - gray if args.invert else gray), a

    moved = 0
    max_displacement = 0.0
    for v in bm.verts:
        # Only vertices on the front face are moved. Vertices on the outer
        # stone boundary remain fixed because the feather reaches zero there.
        if not any(f.normal.z > 0.90 for f in v.link_faces):
            continue
        x, y = float(v.co.x), float(v.co.y)
        if x < left or x > right or y < bottom or y > top:
            continue
        u = (x - left) / relief_w
        vv = (y - bottom) / relief_h
        gray, alpha = sample(u, vv)
        edge_distance = min(u, 1.0 - u, vv, 1.0 - vv) * min(relief_w, relief_h)
        fade = smoothstep(edge_distance / feather)
        amount = depth * gray * alpha * fade
        if amount > 1e-9:
            v.co.z -= amount
            moved += 1
            max_displacement = max(max_displacement, amount)

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    after = stats(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=os.path.abspath(args.out), export_selected_objects=True)
    else:
        bpy.ops.export_mesh.stl(filepath=os.path.abspath(args.out), use_selection=True)

    report = {
        "blender_version": bpy.app.version_string,
        "method": "local front-surface subdivision + image heightfield displacement; no Boolean operation",
        "target": os.path.abspath(args.target),
        "image": os.path.abspath(args.image),
        "image_size_px": image_size,
        "parameters": {
            "depth_mm": args.depth_mm,
            "width_percent": args.width_percent,
            "subdivision_cuts": args.subdivisions,
            "invert": args.invert,
            "feather_percent": args.feather_percent,
        },
        "relief_bounds_xy_m": [round(left, 6), round(bottom, 6), round(right, 6), round(top, 6)],
        "front_faces_detected": len(front_faces),
        "vertices_displaced": moved,
        "max_actual_displacement_mm": round(max_displacement * 1000.0, 4),
        "front_subdivision_ms": round(subdiv_ms, 2),
        "total_ms": round((time.perf_counter() - started) * 1000.0, 2),
        "before": before,
        "after": after,
        "closed_manifold": after["faces"] > 0 and after["non_manifold_edges"] == 0 and after["boundary_edges"] == 0 and after["wire_edges"] == 0,
        "output": os.path.abspath(args.out),
    }
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("[LOCAL SURFACE RELIEF] " + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
