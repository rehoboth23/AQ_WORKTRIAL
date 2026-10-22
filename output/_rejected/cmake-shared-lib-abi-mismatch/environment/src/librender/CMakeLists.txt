add_library(render SHARED render.c)
target_include_directories(render PUBLIC ${CMAKE_SOURCE_DIR} ${CMAKE_SOURCE_DIR}/librender)
target_link_libraries(render PUBLIC math)
