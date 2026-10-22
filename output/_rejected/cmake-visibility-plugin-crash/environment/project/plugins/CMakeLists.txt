set(PLUGIN_DIR ${CMAKE_BINARY_DIR}/plugins)
file(MAKE_DIRECTORY ${PLUGIN_DIR})

add_library(trim_filter MODULE trim_filter.cpp)
target_include_directories(trim_filter PRIVATE ${PROJECT_SOURCE_DIR}/include)
set_target_properties(trim_filter PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${PLUGIN_DIR})

add_library(uppercase_filter MODULE uppercase_filter.cpp)
target_include_directories(uppercase_filter PRIVATE ${PROJECT_SOURCE_DIR}/include)
set_target_properties(uppercase_filter PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${PLUGIN_DIR})
