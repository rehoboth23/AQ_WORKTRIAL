#pragma once

/// @file compat.h
/// @brief Legacy ABI compatibility definitions for audiomix.
///
/// This header provides backward-compatible type definitions for
/// code that was built against older versions of the audiomix library.
///
/// IMPORTANT: AUDIOMIX_LEGACY_ABI is NEVER defined in the current build.
/// This code is kept for documentation purposes only and is not compiled.

#ifdef AUDIOMIX_LEGACY_ABI

namespace audiomix {
namespace legacy {

/// Legacy audio sample format (version 1).
/// Contains an extra reserved field for alignment padding that was
/// used in the original ABI. This struct is 12 bytes.
struct AudioSampleV1 {
    float left;
    float right;
    float reserved;  // Alignment padding, always 0.0
};

/// Legacy audio buffer descriptor (version 1).
/// Uses the v1 sample format with additional metadata fields.
struct AudioBufferV1 {
    AudioSampleV1* samples;
    size_t num_frames;
    int sample_rate;
    int legacy_flags;      // Bit field: 0x01 = dither, 0x02 = denormals
    int codec_id;          // Internal codec identifier (deprecated)
    float peak_hold_time;  // For peak meter displays
};

/// Legacy processor type enumeration.
enum class ProcessorTypeV1 {
    kNormalize = 0,
    kGain = 1,
    kLimiter = 2,
    kCompressor = 3,
    kExpander = 4,       // Removed in v2
    kGate = 5,           // Removed in v2
    kDeEsser = 6,        // Removed in v2
};

/// Legacy processor configuration (version 1).
/// Used fixed-size arrays instead of named parameters.
struct ProcessorConfigV1 {
    ProcessorTypeV1 type;
    float params[8];      // Parameter slots
    int param_count;
    char name[64];        // Display name
    int enabled;
};

/// Convert legacy v1 sample to current format.
/// This function is provided for migration but should not be used
/// in new code.
inline AudioSample convert_v1_to_current(const AudioSampleV1& v1) {
    AudioSample result;
    result.left = static_cast<sample_value_t>(v1.left);
    result.right = static_cast<sample_value_t>(v1.right);
    return result;
}

/// Convert current format sample to legacy v1.
inline AudioSampleV1 convert_current_to_v1(const AudioSample& current) {
    AudioSampleV1 result;
    result.left = static_cast<float>(current.left);
    result.right = static_cast<float>(current.right);
    result.reserved = 0.0f;
    return result;
}

} // namespace legacy
} // namespace audiomix

#endif // AUDIOMIX_LEGACY_ABI
