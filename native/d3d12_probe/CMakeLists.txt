cmake_minimum_required(VERSION 3.24)
project(orion_d3d12_probe LANGUAGES CXX)

if(NOT WIN32)
  message(FATAL_ERROR "Orion D3D12 Probe is Windows-only.")
endif()

add_executable(orion-d3d12-probe main.cpp)
target_compile_features(orion-d3d12-probe PRIVATE cxx_std_17)
target_compile_definitions(orion-d3d12-probe PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
target_link_libraries(orion-d3d12-probe PRIVATE d3d12 dxgi)
if(MSVC)
  target_compile_options(orion-d3d12-probe PRIVATE /W4 /permissive- /EHsc)
endif()
