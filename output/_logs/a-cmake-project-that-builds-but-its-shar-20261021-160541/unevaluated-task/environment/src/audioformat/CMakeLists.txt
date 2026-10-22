add_library(audioformat SHARED
    wav_reader.cpp
    wav_writer.cpp
    format.cpp
    runner.cpp
)

target_include_directories(audioformat PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

target_link_libraries(audioformat PUBLIC audiomix)
