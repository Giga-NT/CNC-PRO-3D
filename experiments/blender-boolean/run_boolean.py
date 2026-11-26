import argparse
import json
import os
import sys
import time

import bpy
import bmesh


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser(description="Blender Exact Boolean benchmark for CNC PRO 3D")
    parser.add_argument("--target", required=True, help="Target STL exported from CNC PRO 3D")
    parser.add_argument("--cutter", required=True, help="Cutter STL exported from CNC PRO 3D")
    parser.add_argument("--out", default="cnc_blender_exact_result.stl", help="Output STL")
    parser.add_argument("--report", default="cnc_blender_exact_report.json", help="JSON report")
    return parser.parse_args(argv)


def import_stl(path, name):
    before = set(bpy.data.objects)
    if hasattr(bpy.ops.wm, "stl_import"):
        bpy.ops.wm.stl_import(filepath=os.path.abspath(path))
    elif hasattr(bpy.ops.import_mesh, "stl"):
        bpy.ops.import_mesh.stl(filepath=os.path.abspath(path))
    else:
        raise RuntimeError("STL import operator is unavailable in this Blender build")
    created = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    if not created:
        raise RuntimeError("No mesh objects imported from " + path)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in created:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    if len(created) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    obj.data.name = name + "_Mesh"
    return obj


def mesh_stats(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
    boundary = sum(1 for edge in bm.edges if edge.is_boundary)
    wire = sum(1 for edge in bm.edges if edge.is_wire)
    stats = {
        "vertices": len(bm.verts),
        "edges": len(bm.edges),
        "faces": len(bm.faces),
        "triangles": sum(max(0, len(face.verts) - 2) for face in bm.faces),
        "non_manifold_edges": non_manifold,
        "boundary_edges": boundary,
        "wire_edges": wire,
        "dimensions": [round(float(v), 6) for v in obj.dimensions],
    }
    bm.free()
    return stats


def export_stl(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=os.path.abspath(path), export_selected_objects=True)
    elif hasattr(bpy.ops.export_mesh, "stl"):
        bpy.ops.export_mesh.stl(filepath=os.path.abspath(path), use_selection=True)
    else:
        raise RuntimeError("STL export operator is unavailable in this Blender build")


def main():
    args = parse_args()
    for path in (args.target, args.cutter):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    target = import_stl(args.target, "CNC_Target")
    cutter = import_stl(args.cutter, "CNC_Cutter")

    report = {
        "blender_version": bpy.app.version_string,
        "target_input": os.path.abspath(args.target),
        "cutter_input": os.path.abspath(args.cutter),
        "target_before": mesh_stats(target),
        "cutter_before": mesh_stats(cutter),
    }
    print("[BLENDER BOOLEAN] Input stats:")
    print(json.dumps({k: report[k] for k in ("target_before", "cutter_before")}, ensure_ascii=False, indent=2))

    modifier = target.modifiers.new(name="CNC_Exact_Difference", type="BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter

    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target

    started = time.perf_counter()
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    report["boolean_solver"] = "EXACT"
    report["boolean_ms"] = round(elapsed_ms, 3)
    report["result"] = mesh_stats(target)
    report["output_stl"] = os.path.abspath(args.out)

    if report["result"]["faces"] == 0:
        raise RuntimeError("Boolean returned an empty mesh; report: " + json.dumps(report, ensure_ascii=False))

    export_stl(target, args.out)
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("[BLENDER BOOLEAN] Exact Difference: %.3f ms" % elapsed_ms)
    print("[BLENDER BOOLEAN] Result stats:")
    print(json.dumps(report["result"], ensure_ascii=False, indent=2))
    print("[BLENDER BOOLEAN] STL:", os.path.abspath(args.out))
    print("[BLENDER BOOLEAN] Report:", os.path.abspath(args.report))


if __name__ == "__main__":
    main()
