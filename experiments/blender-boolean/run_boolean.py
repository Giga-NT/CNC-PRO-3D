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
    parser = argparse.ArgumentParser(description="Blender Exact Boolean diagnostic for CNC PRO 3D")
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
    bm.normal_update()
    non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
    boundary = sum(1 for edge in bm.edges if edge.is_boundary)
    wire = sum(1 for edge in bm.edges if edge.is_wire)

    world_points = [obj.matrix_world @ vert.co for vert in bm.verts]
    if world_points:
        mins = [min(float(p[i]) for p in world_points) for i in range(3)]
        maxs = [max(float(p[i]) for p in world_points) for i in range(3)]
        bounds = {
            "min": [round(v, 6) for v in mins],
            "max": [round(v, 6) for v in maxs],
            "size": [round(maxs[i] - mins[i], 6) for i in range(3)],
        }
    else:
        bounds = None

    try:
        signed_volume = float(bm.calc_volume(signed=True))
    except Exception:
        signed_volume = None

    stats = {
        "object_name": obj.name,
        "vertices": len(bm.verts),
        "edges": len(bm.edges),
        "faces": len(bm.faces),
        "triangles": sum(max(0, len(face.verts) - 2) for face in bm.faces),
        "non_manifold_edges": non_manifold,
        "boundary_edges": boundary,
        "wire_edges": wire,
        "signed_volume": round(signed_volume, 9) if signed_volume is not None else None,
        "world_bounds": bounds,
    }
    bm.free()
    return stats


def recalculate_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    result = bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # Blender versions may return None for this operator; count the mesh faces
    # independently so diagnostics remain compatible across 4.x/5.x.
    affected = len(result.get("faces", [])) if isinstance(result, dict) else len(bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return affected


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
        "target_before_recalc": mesh_stats(target),
        "cutter_before_recalc": mesh_stats(cutter),
    }

    print("[BLENDER BOOLEAN] Input stats before normal recalculation:")
    print(json.dumps({
        "target": report["target_before_recalc"],
        "cutter": report["cutter_before_recalc"],
    }, ensure_ascii=False, indent=2))

    report["target_recalc_faces"] = recalculate_normals(target)
    report["cutter_recalc_faces"] = recalculate_normals(cutter)
    report["target_after_recalc"] = mesh_stats(target)
    report["cutter_after_recalc"] = mesh_stats(cutter)

    print("[BLENDER BOOLEAN] Input stats after normal recalculation:")
    print(json.dumps({
        "target_recalc_faces": report["target_recalc_faces"],
        "cutter_recalc_faces": report["cutter_recalc_faces"],
        "target": report["target_after_recalc"],
        "cutter": report["cutter_after_recalc"],
    }, ensure_ascii=False, indent=2))

    modifier = target.modifiers.new(name="CNC_Exact_Difference", type="BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter

    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.context.view_layer.update()

    started = time.perf_counter()
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.context.view_layer.update()
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    report["boolean_solver"] = "EXACT"
    report["boolean_operation"] = "DIFFERENCE"
    report["boolean_ms"] = round(elapsed_ms, 3)
    report["result"] = mesh_stats(target)
    report["output_stl"] = os.path.abspath(args.out)

    if report["result"]["faces"] == 0:
        raise RuntimeError("Boolean returned an empty mesh; report: " + json.dumps(report, ensure_ascii=False))

    export_stl(target, args.out)
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("[BLENDER BOOLEAN] Exact Difference after normal recalculation: %.3f ms" % elapsed_ms)
    print("[BLENDER BOOLEAN] Result stats:")
    print(json.dumps(report["result"], ensure_ascii=False, indent=2))
    print("[BLENDER BOOLEAN] STL:", os.path.abspath(args.out))
    print("[BLENDER BOOLEAN] Report:", os.path.abspath(args.report))


if __name__ == "__main__":
    main()
