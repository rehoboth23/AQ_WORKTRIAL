#pragma once

/// @file audiomix.h
/// @brief Main public header for the audiomix audio processing library.
///
/// This header aggregates all public audiomix headers and provides
/// the library version information. Include this header to get access
/// to all audiomix types and functions.
///
/// NOTE: AUDIOMIX_USE_DOUBLE must be defined consistently across all
/// translation units that include sample.h, otherwise struct layouts
/// will disagree and audio data will be corrupted at library boundaries.

#include "sample.h"
#include "processor.h"
#include "pipeline.h"
#include "api.h"
#include "analyze.h"

/// Library version information
#define AUDIOMIX_VERSION_MAJOR 1
#define AUDIOMIX_VERSION_MINOR 0
#define AUDIOMIX_VERSION_PATCH 0
#define AUDIOMIX_VERSION "1.0.0"

namespace audiomix {

/// Returns the library version string.
inline const char* version() {
    return AUDIOMIX_VERSION;
}

/// Returns the configured precision mode.
/// @return "double" if AUDIOMIX_USE_DOUBLE is defined, "float" otherwise
inline const char* precision_mode() {
#ifdef AUDIOMIX_USE_DOUBLE
    return "double";
#else
    return "float";
#endif
}

/// Returns the size of AudioSample in bytes for the current configuration.
inline size_t audio_sample_size() {
    return sizeof(AudioSample);
}

} // namespace audiomix
