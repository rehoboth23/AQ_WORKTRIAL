add_library(csvtools SHARED csvtools.cpp capi.cpp)
target_include_directories(csvtools PUBLIC ${PROJECT_SOURCE_DIR}/include)
target_compile_definitions(csvtools PRIVATE CSVTOOLS_BUILD=1)

add_executable(csvtools_bin main.cpp)
target_link_libraries(csvtools_bin PRIVATE csvtools dl)
set_target_properties(csvtools_bin PROPERTIES OUTPUT_NAME csvtools)
