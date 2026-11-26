#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/Polygon_mesh_processing/corefinement.h>
#include <CGAL/Polygon_mesh_processing/repair_polygon_soup.h>
#include <CGAL/Polygon_mesh_processing/orient_polygon_soup.h>
#include <CGAL/Polygon_mesh_processing/polygon_soup_to_polygon_mesh.h>
#include <CGAL/Polygon_mesh_processing/orientation.h>
#include <CGAL/Polygon_mesh_processing/self_intersections.h>
#include <CGAL/boost/graph/helpers.h>
#include <CGAL/number_utils.h>

#include <emscripten/emscripten.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <limits>
#include <string>
#include <vector>

namespace PMP = CGAL::Polygon_mesh_processing;
using Kernel = CGAL::Exact_predicates_inexact_constructions_kernel;
using Point = Kernel::Point_3;
using Mesh = CGAL::Surface_mesh<Point>;

namespace {
std::vector<float> result_positions;
std::vector<std::uint32_t> result_indices;
char last_error[512] = "No operation has been run";
double validation_time_ms = 0.0;
double boolean_time_ms = 0.0;

void set_error(const char* message) {
  std::snprintf(last_error, sizeof(last_error), "%s", message ? message : "Unknown CGAL error");
}

bool build_mesh(const float* xyz,
                std::uint32_t vertex_count,
                const std::uint32_t* triangles,
                std::uint32_t index_count,
                Mesh& mesh) {
  if (!xyz || vertex_count < 4) {
    set_error("Input mesh has no usable vertex array");
    return false;
  }

  const std::uint32_t triangle_index_count = index_count ? index_count : vertex_count;
  if (triangle_index_count < 12 || triangle_index_count % 3 != 0) {
    set_error("Input mesh must contain at least four triangles");
    return false;
  }
  if (index_count && !triangles) {
    set_error("Index pointer is missing");
    return false;
  }
  if (!index_count && vertex_count % 3 != 0) {
    set_error("Non-indexed position count is not divisible by three");
    return false;
  }

  std::vector<Point> points;
  points.reserve(vertex_count);
  for (std::uint32_t i = 0; i < vertex_count; ++i) {
    const float x = xyz[static_cast<std::size_t>(i) * 3];
    const float y = xyz[static_cast<std::size_t>(i) * 3 + 1];
    const float z = xyz[static_cast<std::size_t>(i) * 3 + 2];
    if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) {
      set_error("Input mesh contains a non-finite coordinate");
      return false;
    }
    points.emplace_back(static_cast<double>(x), static_cast<double>(y), static_cast<double>(z));
  }

  std::vector<std::vector<std::size_t>> polygons;
  polygons.reserve(triangle_index_count / 3);
  for (std::uint32_t i = 0; i < triangle_index_count; i += 3) {
    const std::uint32_t a = index_count ? triangles[i] : i;
    const std::uint32_t b = index_count ? triangles[i + 1] : i + 1;
    const std::uint32_t c = index_count ? triangles[i + 2] : i + 2;
    if (a >= vertex_count || b >= vertex_count || c >= vertex_count) {
      set_error("Input mesh index is outside the vertex array");
      return false;
    }
    if (a == b || b == c || c == a) {
      set_error("Input mesh contains a triangle with repeated vertex indices");
      return false;
    }
    polygons.push_back({static_cast<std::size_t>(a),
                        static_cast<std::size_t>(b),
                        static_cast<std::size_t>(c)});
  }

  // Three.js meshes may duplicate positions at normal/material seams.
  // Weld exact coincident coordinates before recovering half-edge connectivity.
  PMP::merge_duplicate_points_in_polygon_soup(points, polygons);
  PMP::remove_isolated_points_in_polygon_soup(points, polygons);

  if (!PMP::orient_polygon_soup(points, polygons)) {
    set_error("CGAL could not consistently orient the input triangle soup");
    return false;
  }

  PMP::polygon_soup_to_polygon_mesh(points, polygons, mesh);
  if (mesh.number_of_faces() < 4 || !CGAL::is_triangle_mesh(mesh)) {
    set_error("Input could not be converted to a triangulated Surface_mesh");
    return false;
  }
  if (!CGAL::is_closed(mesh)) {
    set_error("Input mesh is not closed after vertex welding");
    return false;
  }
  if (PMP::does_self_intersect(mesh)) {
    set_error("Input mesh contains self-intersections");
    return false;
  }

  PMP::orient_to_bound_a_volume(mesh);
  if (!PMP::does_bound_a_volume(mesh)) {
    set_error("Input mesh does not bound a valid volume");
    return false;
  }
  return true;
}

void export_mesh(Mesh& mesh) {
  mesh.collect_garbage();
  const std::size_t vertex_count = mesh.number_of_vertices();
  if (vertex_count > std::numeric_limits<std::uint32_t>::max()) {
    throw std::runtime_error("Result exceeds the 32-bit vertex index limit");
  }

  std::vector<std::uint32_t> remap(vertex_count, std::numeric_limits<std::uint32_t>::max());
  result_positions.clear();
  result_indices.clear();
  result_positions.reserve(vertex_count * 3);
  result_indices.reserve(mesh.number_of_faces() * 3);

  for (const auto vertex : mesh.vertices()) {
    const auto id = static_cast<std::uint32_t>(vertex.idx());
    const Point& p = mesh.point(vertex);
    remap[id] = static_cast<std::uint32_t>(result_positions.size() / 3);
    result_positions.push_back(static_cast<float>(CGAL::to_double(p.x())));
    result_positions.push_back(static_cast<float>(CGAL::to_double(p.y())));
    result_positions.push_back(static_cast<float>(CGAL::to_double(p.z())));
  }

  for (const auto face : mesh.faces()) {
    auto h = halfedge(face, mesh);
    for (int corner = 0; corner < 3; ++corner) {
      const auto vertex = target(h, mesh);
      const auto id = static_cast<std::size_t>(vertex.idx());
      if (id >= remap.size() || remap[id] == std::numeric_limits<std::uint32_t>::max()) {
        throw std::runtime_error("Result mesh contains an invalid vertex reference");
      }
      result_indices.push_back(remap[id]);
      h = next(h, mesh);
    }
  }
}
} // namespace

extern "C" {

EMSCRIPTEN_KEEPALIVE
int cgal_run_difference(const float* a_positions,
                        std::uint32_t a_vertex_count,
                        const std::uint32_t* a_indices,
                        std::uint32_t a_index_count,
                        const float* b_positions,
                        std::uint32_t b_vertex_count,
                        const std::uint32_t* b_indices,
                        std::uint32_t b_index_count) {
  result_positions.clear();
  result_indices.clear();
  validation_time_ms = 0.0;
  boolean_time_ms = 0.0;
  set_error("");

  try {
    Mesh a;
    Mesh b;
    Mesh result;

    const double validation_start = emscripten_get_now();
    if (!build_mesh(a_positions, a_vertex_count, a_indices, a_index_count, a) ||
        !build_mesh(b_positions, b_vertex_count, b_indices, b_index_count, b)) {
      validation_time_ms = emscripten_get_now() - validation_start;
      return 2;
    }
    validation_time_ms = emscripten_get_now() - validation_start;

    const double boolean_start = emscripten_get_now();
    const bool success = PMP::corefine_and_compute_difference(a, b, result);
    boolean_time_ms = emscripten_get_now() - boolean_start;
    if (!success || result.number_of_faces() < 4 || !CGAL::is_closed(result)) {
      set_error("CGAL Difference did not produce a closed result");
      return 3;
    }

    PMP::orient_to_bound_a_volume(result);
    if (!PMP::does_bound_a_volume(result) || PMP::does_self_intersect(result)) {
      set_error("CGAL Difference result failed the solid validity checks");
      return 4;
    }

    export_mesh(result);
    if (result_indices.size() < 12 || result_positions.size() < 36) {
      set_error("CGAL Difference returned an empty or degenerate result");
      return 5;
    }
    return 0;
  } catch (const std::exception& error) {
    set_error(error.what());
    return 6;
  } catch (...) {
    set_error("Unknown exception inside CGAL Difference");
    return 7;
  }
}

EMSCRIPTEN_KEEPALIVE
std::uint32_t cgal_result_vertex_count() {
  return static_cast<std::uint32_t>(result_positions.size() / 3);
}

EMSCRIPTEN_KEEPALIVE
std::uint32_t cgal_result_index_count() {
  return static_cast<std::uint32_t>(result_indices.size());
}

EMSCRIPTEN_KEEPALIVE
std::uint32_t cgal_result_positions_ptr() {
  return result_positions.empty() ? 0u :
    static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(result_positions.data()));
}

EMSCRIPTEN_KEEPALIVE
std::uint32_t cgal_result_indices_ptr() {
  return result_indices.empty() ? 0u :
    static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(result_indices.data()));
}

EMSCRIPTEN_KEEPALIVE
const char* cgal_last_error() {
  return last_error;
}

EMSCRIPTEN_KEEPALIVE
double cgal_validation_ms() {
  return validation_time_ms;
}

EMSCRIPTEN_KEEPALIVE
double cgal_boolean_ms() {
  return boolean_time_ms;
}

} // extern "C"
