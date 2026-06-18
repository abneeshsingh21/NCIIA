cmake_minimum_required(VERSION 3.16)
project(nciia-perf VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Build type default
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# ===========================================================================
# Compiler-specific flags (MSVC vs GCC/Clang)
# ===========================================================================
if(MSVC)
    # /EHsc  – enable C++ exception handling (required to catch exceptions in FFI bindings)
    # /O2    – full optimisation for Release
    # /Od /Zi – no optimisation + debug info for Debug
    # /W3    – warning level 3
    add_compile_options(/EHsc /W3)
    add_compile_options($<$<CONFIG:Debug>:/Od> $<$<CONFIG:Debug>:/Zi> $<$<NOT:$<CONFIG:Debug>>:/O2>)
    # Suppress MSVC "unsafe" CRT warnings that pollute build output
    add_definitions(-D_CRT_SECURE_NO_WARNINGS)
else()
    # GCC / Clang flags
    add_compile_options(-Wall -Wextra)
    add_compile_options($<$<CONFIG:Debug>:-g> $<$<CONFIG:Debug>:-O0> $<$<NOT:$<CONFIG:Debug>>:-O3>)
endif()

# ===========================================================================
# Source files
# ===========================================================================
set(STYLOMETRY_SOURCES
    src/stylometry/analyzer.cpp
    src/stylometry/features.cpp
)

set(SIMILARITY_SOURCES
    src/similarity/text_sim.cpp
)

set(HASHING_SOURCES
    src/hashing/fast_hash.cpp
)

set(BINDING_SOURCES
    src/bindings/c_bindings.cpp
)

# ===========================================================================
# Shared library target
# ===========================================================================
add_library(nciia_perf SHARED
    ${STYLOMETRY_SOURCES}
    ${SIMILARITY_SOURCES}
    ${HASHING_SOURCES}
    ${BINDING_SOURCES}
)

target_include_directories(nciia_perf PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# ===========================================================================
# Tests (optional; enable by passing -DBUILD_TESTS=ON)
# ===========================================================================
option(BUILD_TESTS "Build test executables" OFF)
if(BUILD_TESTS)
    enable_testing()
    add_executable(test_stylometry tests/test_stylometry.cpp)
    target_include_directories(test_stylometry PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)
    target_link_libraries(test_stylometry PRIVATE nciia_perf)
    add_test(NAME StylometryTest COMMAND test_stylometry)
endif()

# ===========================================================================
# Install rules
# ===========================================================================
install(TARGETS nciia_perf
    RUNTIME DESTINATION bin   # .dll on Windows
    LIBRARY DESTINATION lib   # .so on Linux/macOS
    ARCHIVE DESTINATION lib   # .lib on Windows
)
install(DIRECTORY include/ DESTINATION include)
