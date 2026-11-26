cmake_minimum_required(VERSION 3.22)
project(cnc_cgal_wasm LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)
set(BUILD_DOC OFF CACHE BOOL "Do not build CGAL documentation" FORCE)
set(CGAL_DISABLE_GMP ON CACHE BOOL "Use CGAL without GMP/MPFR" FORCE)
set(CGAL_ENABLE_TESTING OFF CACHE BOOL "Do not build CGAL tests" FORCE)
set(CGAL_HAS_NO_THREADS ON CACHE BOOL "Build single-threaded CGAL for WebAssembly workers" FORCE)
set(CGAL_DO_NOT_USE_BOOST_MP OFF CACHE BOOL "Keep CGAL Boost multiprecision support enabled" FORCE)

FetchContent_Declare(
  cgal_src
  GIT_REPOSITORY https://github.com/CGAL/cgal.git
  GIT_TAG v6.2.1
  GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(cgal_src)

# CGAL's branch-build configuration generates CGALConfig.cmake and config.h
# in the FetchContent binary directory, and exports every package include dir.
find_package(CGAL CONFIG REQUIRED PATHS "${cgal_src_BINARY_DIR}" NO_DEFAULT_PATH)

add_executable(cgal_boolean src/cgal_boolean.cpp)
target_link_libraries(cgal_boolean PRIVATE CGAL::CGAL)
target_compile_options(cgal_boolean PRIVATE -O3 -fexceptions)
target_link_options(cgal_boolean PRIVATE
  -O3
  -fexceptions
  -sDISABLE_EXCEPTION_CATCHING=0
  -sMODULARIZE=1
  -sEXPORT_ES6=1
  -sEXPORT_NAME=createCGALModule
  -sENVIRONMENT=web,worker
  -sALLOW_MEMORY_GROWTH=1
  -sINITIAL_MEMORY=268435456
  -sMAXIMUM_MEMORY=3221225472
  -sSTACK_SIZE=16777216
  -sFILESYSTEM=0
  -sNO_EXIT_RUNTIME=1
  "-sEXPORTED_FUNCTIONS=['_malloc','_free','_cgal_run_difference','_cgal_result_vertex_count','_cgal_result_index_count','_cgal_result_positions_ptr','_cgal_result_indices_ptr','_cgal_last_error','_cgal_validation_ms','_cgal_boolean_ms']"
  "-sEXPORTED_RUNTIME_METHODS=['UTF8ToString']"
)

set_target_properties(cgal_boolean PROPERTIES
  SUFFIX ".js"
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/dist"
)
