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

# Emscripten does not search the host system include paths by default.
# Copy Boost's header-only tree into the build directory so CGAL can include it
# without exposing the host's full /usr/include to the cross-compiler.
find_path(BOOST_INCLUDE_ROOT NAMES boost/config.hpp PATHS /usr/include /usr/local/include REQUIRED)
file(COPY "${BOOST_INCLUDE_ROOT}/boost" DESTINATION "${CMAKE_BINARY_DIR}/boost-include")

# CGAL branch builds do not provide an installed CGALConfig.cmake package.
# Expose the generated headers and each package's headers directly instead.
file(GLOB CGAL_PACKAGE_INCLUDE_DIRS "${cgal_src_SOURCE_DIR}/*/include")
list(APPEND CGAL_PACKAGE_INCLUDE_DIRS "${cgal_src_BINARY_DIR}/include")
list(APPEND CGAL_PACKAGE_INCLUDE_DIRS "${cgal_src_SOURCE_DIR}/Installation/include")
list(REMOVE_DUPLICATES CGAL_PACKAGE_INCLUDE_DIRS)

add_executable(cgal_boolean src/cgal_boolean.cpp)
target_include_directories(cgal_boolean SYSTEM PRIVATE ${CGAL_PACKAGE_INCLUDE_DIRS} "${CMAKE_BINARY_DIR}/boost-include")
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
