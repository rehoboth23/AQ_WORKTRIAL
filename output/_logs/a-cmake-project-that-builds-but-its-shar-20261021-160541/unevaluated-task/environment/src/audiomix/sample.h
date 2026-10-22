#pragma once

/// @file sample.h
/// @brief Audio sample type definitions for the audiomix library.
///
/// The sample_value_t type alias controls the internal precision of audio
/// processing. When AUDIOMIX_USE_DOUBLE is defined, all sample values are
/// stored and processed as double-precision floating point. Otherwise,
/// single-precision float is used.
///
/// IMPORTANT: All translation units that exchange AudioSample buffers must
/// agree on the definition of sample_value_t. Mixing definitions across
/// library boundaries results in corrupted audio data.

#include <cstdint>
#include <cstddef>
#include <cmath>

#ifdef AUDIOMIX_USE_DOUBLE
using sample_value_t = double;
#else
using sample_value_t = float;
#endif

/// Represents a single stereo audio frame with left and right channel values.
struct AudioSample {
    sample_value_t left;
    sample_value_t right;
};

/// Metadata describing an audio buffer's format.
struct AudioBufferInfo {
    int sample_rate;
    int channels;
    size_t num_frames;
    int bits_per_sample;
};

/// Constants for audio processing
namespace AudioConstants {
    constexpr sample_value_t PI = sample_value_t(3.14159265358979323846);
    constexpr sample_value_t TWO_PI = sample_value_t(6.28318530717958647692);
    constexpr sample_value_t LOG10_20 = sample_value_t(20.0);
    constexpr sample_value_t DB_EPSILON = sample_value_t(1e-10);
    constexpr sample_value_t SILENCE_THRESHOLD = sample_value_t(1e-9);
    constexpr int16_t PCM16_MAX = 32767;
    constexpr int16_t PCM16_MIN = -32768;
    constexpr sample_value_t PCM16_NORM = sample_value_t(32768.0);
}

/// Convert a linear amplitude value to decibels.
inline sample_value_t linear_to_db(sample_value_t linear) {
    if (linear <= AudioConstants::DB_EPSILON) {
        return -sample_value_t(120.0); // Floor at -120 dB
    }
    return AudioConstants::LOG10_20 * std::log10(linear);
}

/// Convert a decibel value to linear amplitude.
inline sample_value_t db_to_linear(sample_value_t db) {
    return std::pow(sample_value_t(10.0), db / sample_value_t(20.0));
}

/// Check if a value represents silence (below threshold).
inline bool is_silence(sample_value_t value) {
    return std::abs(value) < AudioConstants::SILENCE_THRESHOLD;
}
