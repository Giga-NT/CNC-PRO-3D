cmake_minimum_required(VERSION 3.22)
project(cnc_cgal_wasm LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)
FetchContent_Declare(
  cgal_src
  GIT_REPOSITORY https://github.com/CGAL/cgal.git
  GIT_TAG v6.2.1
  GIT_SHALLOW TRUE
)
FetchContent_GetProperties(cgal_src)
if(NOT cgal_src_POPULATED)
  FetchContent_Populate(cgal_src)
endif()

find_package(Boost 1.74 REQUIRED)

add_executable(cgal_boolean src/cgal_boolean.cpp)
target_include_directories(cgal_boolean SYSTEM PRIVATE
  "${cgal_src_SOURCE_DIR}/include"
  ${Boost_INCLUDE_DIRS}
)
target_compile_definitions(cgal_boolean PRIVATE
  CGAL_DISABLE_GMP
  CGAL_USE_BOOST_MP
)
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
