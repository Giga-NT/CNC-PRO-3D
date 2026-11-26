"""Convert CNC PRO STL operands to triangle OBJ files for Kigumi.

Run through Blender in background mode. Coordinates are written in world space;
no decimation, welding, smoothing, or face deletion is performed here.
"""
import argparse
import json
import os
import sys

import bpy


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--cutter", required=True)
    parser.add_argument("--target-obj", required=True)
    parser.add_argument("--cutter-obj", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(argv)


def import_stl(path, name):
    before = set(bpy.data.objects)
    if hasattr(bpy.ops.wm, "stl_import"):
        bpy.ops.wm.stl_import(filepath=os.path.abspath(path))
    elif hasattr(bpy.ops.import_mesh, "stl"):
        bpy.ops.import_mesh.stl(filepath=os.path.abspath(path))
    else:
        raise RuntimeError("Blender STL import operator is unavailable")
    objects = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if not objects:
        raise RuntimeError("No mesh imported from " + path)
    for i, obj in enumerate(objects):
        obj.name = name if len(objects) == 1 else f"{name}_{i}"
    return objects


def write_obj(objects, path):
    vertex_offset = 0
    vertices_written = 0
    triangles_written = 0
    with open(path, "w", encoding="utf-8", newline="\n") as out:
        out.write("# CNC PRO 3D Kigumi experiment input; world-space coordinates\n")
        for obj in objects:
            out.write(f"o {obj.name}\n")
            depsgraph = bpy.context.evaluated_depsgraph_get()
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            try:
                matrix = obj.matrix_world
                for vertex in mesh.vertices:
                    p = matrix @ vertex.co
                    out.write(f"v {p.x:.9g} {p.y:.9g} {p.z:.9g}\n")
                    vertices_written += 1
                for poly in mesh.polygons:
                    ids = list(poly.vertices)
                    if len(ids) < 3:
                        continue
                    for i in range(1, len(ids) - 1):
                        a = vertex_offset + ids[0] + 1
                        b = vertex_offset + ids[i] + 1
                        c = vertex_offset + ids[i + 1] + 1
                        out.write(f"f {a} {b} {c}\n")
                        triangles_written += 1
                vertex_offset += len(mesh.vertices)
            finally:
                evaluated.to_mesh_clear()
    return {
        "objects": len(objects),
        "vertices": vertices_written,
        "triangles": triangles_written,
        "path": os.path.abspath(path),
    }


def main():
    args = parse_args()
    for path in (args.target, args.cutter):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    target_objects = import_stl(args.target, "CNC_Target")
    cutter_objects = import_stl(args.cutter, "CNC_Cutter")

    report = {
        "blender_version": bpy.app.version_string,
        "target": write_obj(target_objects, args.target_obj),
        "cutter": write_obj(cutter_objects, args.cutter_obj),
        "processing": "coordinate-preserving STL-to-OBJ conversion; no mesh repair or reduction",
    }
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print("[KIGUMI INPUT PREP]")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
