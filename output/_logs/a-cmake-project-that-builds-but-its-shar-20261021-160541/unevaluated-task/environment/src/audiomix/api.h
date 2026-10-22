#pragma once

/// @file api.h
/// @brief C API for the audiomix library.
///
/// These functions provide a C-linkage interface to the audiomix library,
/// allowing it to be used from C code and enabling dynamic loading via dlsym.
/// All pointers are passed as void* for opacity.

#include <cstddef>

/// API export macro.
/// When building the library, symbols are marked with default visibility.
/// When using the library, the macro expands to nothing.
#if defined(_WIN32) || defined(_WIN64)
    #ifdef AUDIOMIX_BUILDING
        #define AUDIOMIX_API __declspec(dllexport)
    #else
        #define AUDIOMIX_API __declspec(dllimport)
    #endif
#else
    #define AUDIOMIX_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

/// Create an audio processor of the specified type.
/// @param type Processor type name ("normalize", "gain", "limiter", "compressor")
/// @param param Processor parameter value (meaning depends on type)
/// @return Opaque pointer to the processor, or NULL on failure
AUDIOMIX_API void* audiomix_init_processor(const char* type, double param);

/// Destroy an audio processor previously created by audiomix_init_processor.
/// @param proc Opaque processor pointer
AUDIOMIX_API void audiomix_free_processor(void* proc);

/// Allocate an audio sample buffer with the appropriate size and alignment.
/// The buffer is zero-initialized and large enough for num_frames stereo frames.
/// @param num_frames Number of audio frames the buffer should hold
/// @return Pointer to the allocated buffer, or NULL on failure
AUDIOMIX_API void* audiomix_init_buffer(size_t num_frames);

/// Free an audio sample buffer previously allocated by audiomix_init_buffer.
/// @param buffer Pointer to the buffer to free
AUDIOMIX_API void audiomix_free_buffer(void* buffer);

/// Process an audio buffer using the given processor.
/// The processing is done in-place; the buffer contents are modified.
/// @param proc Opaque processor pointer
/// @param buffer Audio sample buffer
/// @param num_frames Number of frames in the buffer
AUDIOMIX_API void audiomix_process_samples(void* proc, void* buffer, size_t num_frames);

/// Analyze an audio file (declared here for completeness; defined in analyze.h).
/// @param filepath Path to the WAV file
/// @param result Buffer for formatted result string
/// @param result_size Size of result buffer
/// @return 0 on success, -1 on failure
AUDIOMIX_API int audiomix_analyze_file(const char* filepath, char* result, size_t result_size);

#ifdef __cplusplus
}
#endif
