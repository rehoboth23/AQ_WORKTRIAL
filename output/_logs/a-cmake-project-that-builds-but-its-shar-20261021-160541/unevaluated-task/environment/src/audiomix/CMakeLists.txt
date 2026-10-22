add_library(audiomix SHARED
    processor.cpp
    pipeline.cpp
    analyze.cpp
    api.cpp
)

target_include_directories(audiomix PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

target_compile_definitions(audiomix
    PRIVATE AUDIOMIX_BUILDING=1
    PRIVATE AUDIOMIX_USE_DOUBLE=1
)

target_link_options(audiomix PRIVATE
    LINKER:--version-script=${CMAKE_SOURCE_DIR}/audiomix.map
    LINKER:--no-undefined
)

target_link_libraries(audiomix PRIVATE m)
