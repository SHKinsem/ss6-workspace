cmake_minimum_required(VERSION 3.16)
project(ss6_workspace LANGUAGES CXX)

# Umbrella build for the SS6 packages. Each package stays independently buildable;
# can-device-core is added first so the others reuse one can_device_core target.
include(CTest)

set(SS6_REPOS "${CMAKE_CURRENT_SOURCE_DIR}/repos")
foreach(package can-device-core zdt-x-driver dji-motor-driver)
  if(NOT EXISTS "${SS6_REPOS}/${package}/CMakeLists.txt")
    message(FATAL_ERROR "repos/${package} is missing; run: git submodule update --init")
  endif()
endforeach()

add_subdirectory("${SS6_REPOS}/can-device-core" can-device-core)
add_subdirectory("${SS6_REPOS}/zdt-x-driver" zdt-x-driver)
add_subdirectory("${SS6_REPOS}/dji-motor-driver" dji-motor-driver)

# ss6-bsp finds the drivers through these cache paths when its demo is enabled.
set(CAN_DEVICE_CORE_DIR "${SS6_REPOS}/can-device-core" CACHE PATH "" FORCE)
set(ZDT_X_DRIVER_DIR "${SS6_REPOS}/zdt-x-driver" CACHE PATH "" FORCE)
set(DJI_MOTOR_DRIVER_DIR "${SS6_REPOS}/dji-motor-driver" CACHE PATH "" FORCE)
add_subdirectory("${SS6_REPOS}/ss6-bsp" ss6-bsp)
