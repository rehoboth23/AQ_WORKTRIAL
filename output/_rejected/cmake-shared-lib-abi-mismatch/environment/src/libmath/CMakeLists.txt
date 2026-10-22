add_library(math SHARED math_ops.c)
target_include_directories(math PUBLIC ${CMAKE_SOURCE_DIR} ${CMAKE_SOURCE_DIR}/libmath)
target_compile_definitions(math PRIVATE USE_SINGLE_PRECISION)
target_link_libraries(math PRIVATE m)
