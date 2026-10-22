cmake_minimum_required(VERSION 3.10)
project(geom_app C)

set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

add_subdirectory(libmath)
add_subdirectory(librender)

add_executable(geom_app main.c)
target_include_directories(geom_app PRIVATE ${CMAKE_SOURCE_DIR})
target_link_libraries(geom_app PRIVATE render)
