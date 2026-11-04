cmake_minimum_required(VERSION 3.24)
project(eglantine_nx2_core_check LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
include(FetchContent)
file(READ "${EDEN_SOURCE}/cpmfile.json" packages)
string(JSON catch_version GET "${packages}" catch2 version)
string(JSON catch_hash GET "${packages}" catch2 hash)
set(CATCH_BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(CATCH_INSTALL_DOCS OFF CACHE BOOL "" FORCE)
set(CATCH_INSTALL_EXTRAS OFF CACHE BOOL "" FORCE)
FetchContent_Declare(Catch2
    URL "https://github.com/catchorg/Catch2/archive/refs/tags/${catch_version}.tar.gz"
    URL_HASH "SHA512=${catch_hash}")
FetchContent_MakeAvailable(Catch2)
file(GLOB ampere_tests CONFIGURE_DEPENDS "${EDEN_SOURCE}/src/tests/video_core/ampere_*.cpp")
# These two integration tests link the complete shader compiler and run in upstream tests.
# This host check exercises the header-only native capture/lowering and memory helpers.
list(FILTER ampere_tests EXCLUDE REGEX "ampere_(bindless_tex|sured)\\.cpp$")
# Newer Eglantine has more tests that translate or emit whole programs: they need the
# compiled shader compiler too.
foreach(test IN LISTS ampere_tests)
    file(READ "${test}" test_source)
    if(test_source MATCHES "#include \"shader_recompiler/(backend|frontend/maxwell|ir_opt|object_pool|host_translate_info)")
        list(REMOVE_ITEM ampere_tests "${test}")
    endif()
endforeach()
# Newer Eglantine dropped these; the check takes those its source still has.
set(core_tests)
foreach(test core/read_traps core/nx2_readback_cache core/nx2_core_readback_capacity
        video_core/nx2_gpu_mappings video_core/nx2_command_ranges video_core/nx2_command_sync
        video_core/nx2_sparse_region video_core/memory_budget)
    if(EXISTS "${EDEN_SOURCE}/src/tests/${test}.cpp")
        list(APPEND core_tests "${EDEN_SOURCE}/src/tests/${test}.cpp")
    endif()
endforeach()
list(LENGTH ampere_tests ampere_count)
list(LENGTH core_tests core_count)
message(STATUS "nx2 core check: ${ampere_count} Ampere and ${core_count} core tests")
if(ampere_count EQUAL 0)
    message(FATAL_ERROR "No header-only Ampere tests left to run")
endif()
add_executable(nx2-core-check ${ampere_tests} ${core_tests})
file(GLOB boost_includes "${DEPENDENCY_SOURCE}/.cache/cpm/boost/*/libs/*/include")
target_include_directories(nx2-core-check PRIVATE "${EDEN_SOURCE}/src" "${FMT_INCLUDE}" ${boost_includes})
target_link_libraries(nx2-core-check PRIVATE Catch2::Catch2WithMain)
