import argparse
import json
import os
import sys
import time

import bpy
import bmesh
from mathutils.bvhtree import BVHTree


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



def topology_diagnostics(obj, max_samples=12):
    """Inspect edge incidence, connected face islands and non-adjacent self-overlaps."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    incidence = {}
    suspicious_edges = []
    for edge in bm.edges:
        linked = len(edge.link_faces)
        incidence[str(linked)] = incidence.get(str(linked), 0) + 1
        if linked != 2 and len(suspicious_edges) < max_samples:
            face_details = []
            for face in edge.link_faces:
                face_details.append({
                    "face_index": int(face.index),
                    "area": round(float(face.calc_area()), 12),
                    "normal": [round(float(face.normal[i]), 6) for i in range(3)],
                    "vertices": [[round(float(v.co[i]), 6) for i in range(3)] for v in face.verts],
                })
            suspicious_edges.append({
                "linked_faces": linked,
                "vertices": [[round(float(v.co[i]), 6) for i in range(3)] for v in edge.verts],
                "linked_face_details": face_details,
            })

    # Count connected face islands by traversing face adjacency across shared edges.
    unseen = set(bm.faces)
    islands = []
    while unseen:
        seed = unseen.pop()
        stack = [seed]
        count = 0
        while stack:
            face = stack.pop()
            count += 1
            for edge in face.edges:
                for neighbor in edge.link_faces:
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        stack.append(neighbor)
        islands.append(count)
    islands.sort(reverse=True)

    # BVH overlap includes neighboring triangles; discard pairs sharing any vertex.
    overlap_count = 0
    overlap_samples = []
    try:
        tree = BVHTree.FromBMesh(bm, epsilon=1e-7)
        pairs = tree.overlap(tree)
        for a, b in pairs:
            if a >= b:
                continue
            fa, fb = bm.faces[a], bm.faces[b]
            if set(fa.verts).intersection(fb.verts):
                continue
            overlap_count += 1
            if len(overlap_samples) < max_samples:
                overlap_samples.append([int(a), int(b)])
    except Exception as exc:
        overlap_error = str(exc)
    else:
        overlap_error = None

    result = {
        "edge_face_incidence_histogram": incidence,
        "edges_not_linked_to_exactly_two_faces": sum(1 for e in bm.edges if len(e.link_faces) != 2),
        "suspicious_edge_samples": suspicious_edges,
        "connected_face_island_count": len(islands),
        "largest_face_islands": islands[:12],
        "non_adjacent_bvh_overlap_pairs": overlap_count,
        "overlap_pair_samples": overlap_samples,
        "overlap_test_error": overlap_error,
    }
    bm.free()
    return result



def boolean_probe(target_source, cutter_source, operation, flip_cutter=False):
    target = target_source.copy()
    target.data = target_source.data.copy()
    bpy.context.collection.objects.link(target)
    cutter = cutter_source.copy()
    cutter.data = cutter_source.data.copy()
    bpy.context.collection.objects.link(cutter)
    target.name = "Probe_Target_" + operation + ("_Flipped" if flip_cutter else "")
    cutter.name = "Probe_Cutter_" + operation + ("_Flipped" if flip_cutter else "")

    if flip_cutter:
        bm = bmesh.new()
        bm.from_mesh(cutter.data)
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
        bm.to_mesh(cutter.data)
        bm.free()
        cutter.data.update()

    modifier = target.modifiers.new(name="Probe_" + operation, type="BOOLEAN")
    modifier.operation = operation
    modifier.solver = "EXACT"
    modifier.object = cutter
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.context.view_layer.update()
    started = time.perf_counter()
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    elapsed = (time.perf_counter() - started) * 1000.0
    stats = mesh_stats(target)
    source_bounds = mesh_stats(target_source)["world_bounds"]
    output = {
        "operation": operation,
        "cutter_normals_flipped": flip_cutter,
        "boolean_ms": round(elapsed, 3),
        "result": stats,
        "result_has_target_bounds": bool(
            stats["world_bounds"] and source_bounds and
            stats["world_bounds"]["min"] == source_bounds["min"] and
            stats["world_bounds"]["max"] == source_bounds["max"]
        ),
    }
    bpy.data.objects.remove(target, do_unlink=True)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return output


def operand_boolean_probes(target, cutter):
    probes = []
    for operation, flip in (("DIFFERENCE", False), ("DIFFERENCE", True), ("INTERSECT", False), ("UNION", False)):
        try:
            probes.append(boolean_probe(target, cutter, operation, flip))
        except Exception as exc:
            probes.append({
                "operation": operation,
                "cutter_normals_flipped": flip,
                "error": str(exc),
            })
    return probes


def make_cutter_repair_variant(source, mode):
    """Build an isolated cutter copy for topology-repair experiments."""
    obj = source.copy()
    obj.data = source.data.copy()
    bpy.context.collection.objects.link(obj)
    obj.name = "Repair_" + mode
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    before = {
        "vertices": len(bm.verts),
        "faces": len(bm.faces),
        "non_manifold_edges": sum(1 for e in bm.edges if not e.is_manifold),
    }
    details = {}
    if mode.startswith("weld_"):
        threshold = float(mode.split("_", 1)[1])
        result = bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=threshold)
        details["welded_vertices"] = len(result.get("targetmap", {}))
    elif mode == "delete_excess_faces_fill":
        bad_edges = [e for e in bm.edges if len(e.link_faces) > 2]
        faces_to_delete = set()
        for edge in bad_edges:
            linked = sorted(edge.link_faces, key=lambda face: face.calc_area())
            # Keep the two largest incident faces on each offending edge.
            faces_to_delete.update(linked[:-2])
        details["deleted_faces"] = len(faces_to_delete)
        if faces_to_delete:
            bmesh.ops.delete(bm, geom=list(faces_to_delete), context="FACES_ONLY")
        boundary_edges = [e for e in bm.edges if e.is_boundary]
        details["boundary_edges_before_fill"] = len(boundary_edges)
        if boundary_edges:
            fill = bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=0)
            details["filled_faces"] = len(fill.get("faces", []))
    elif mode == "delete_all_faces_touching_bad_edges_fill":
        bad_edges = [e for e in bm.edges if len(e.link_faces) != 2]
        faces_to_delete = {face for edge in bad_edges for face in edge.link_faces}
        details["deleted_faces"] = len(faces_to_delete)
        if faces_to_delete:
            bmesh.ops.delete(bm, geom=list(faces_to_delete), context="FACES_ONLY")
        boundary_edges = [e for e in bm.edges if e.is_boundary]
        details["boundary_edges_before_fill"] = len(boundary_edges)
        if boundary_edges:
            fill = bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=0)
            details["filled_faces"] = len(fill.get("faces", []))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    after = mesh_stats(obj)
    return obj, {"mode": mode, "before": before, "after": after, "repair_details": details}


def cutter_repair_boolean_probes(target, cutter):
    results = []
    modes = (
        "weld_0.000001",
        "weld_0.00001",
        "weld_0.0001",
        "delete_excess_faces_fill",
        "delete_all_faces_touching_bad_edges_fill",
    )
    for mode in modes:
        variant = None
        try:
            variant, repair = make_cutter_repair_variant(cutter, mode)
            probe = boolean_probe(target, variant, "DIFFERENCE", flip_cutter=False)
            results.append({"repair": repair, "boolean": probe})
        except Exception as exc:
            results.append({"mode": mode, "error": str(exc)})
        finally:
            if variant is not None:
                bpy.data.objects.remove(variant, do_unlink=True)
    return results


def simple_cube_boolean_test():
    """Control test: subtract one closed cube from another using Blender Exact."""
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
    target = bpy.context.object
    target.name = "Control_Target_Cube"
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.5, 0.0, 0.0))
    cutter = bpy.context.object
    cutter.name = "Control_Cutter_Cube"

    modifier = target.modifiers.new(name="Control_Exact_Difference", type="BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.context.view_layer.update()

    started = time.perf_counter()
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    stats = mesh_stats(target)
    result = {
        "boolean_ms": round(elapsed_ms, 3),
        "result": stats,
        "closed_manifold": stats["faces"] > 0 and stats["non_manifold_edges"] == 0 and stats["boundary_edges"] == 0,
    }
    bpy.data.objects.remove(cutter, do_unlink=True)
    bpy.data.objects.remove(target, do_unlink=True)
    return result

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
        "target_topology_before_recalc": topology_diagnostics(target),
        "cutter_topology_before_recalc": topology_diagnostics(cutter),
        "simple_cube_control": simple_cube_boolean_test(),
        "operand_boolean_probes": operand_boolean_probes(target, cutter),
        "cutter_repair_boolean_probes": cutter_repair_boolean_probes(target, cutter),
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
