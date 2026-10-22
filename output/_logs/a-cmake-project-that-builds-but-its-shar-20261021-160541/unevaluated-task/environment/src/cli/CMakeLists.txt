add_executable(audiomix-cli
    main.cpp
    cli.cpp
)

target_include_directories(audiomix-cli PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

target_link_libraries(audiomix-cli PRIVATE
    audioformat
    audiomix
    dl
)
