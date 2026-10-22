#pragma once

/// @file format.h
/// @brief Audio format utilities for the audioformat library.
///
/// Provides helper functions for audio format conversion, validation,
/// and metadata handling.

#include "audiomix/sample.h"
#include <string>
#include <cstdint>

namespace audioformat {

/// Get a human-readable description of an audio format.
std::string format_description(const audiomix::AudioBufferInfo& info);

/// Validate audio buffer info for processing.
/// @return true if the format is supported, false otherwise
bool validate_format(const audiomix::AudioBufferInfo& info);

/// Compute the duration of an audio buffer in seconds.
inline double duration_seconds(const audiomix::AudioBufferInfo& info) {
    if (info.sample_rate <= 0) return 0.0;
    return static_cast<double>(info.num_frames) / info.sample_rate;
}

/// Compute the number of bytes needed for raw PCM data.
inline size_t pcm_data_size(const audiomix::AudioBufferInfo& info) {
    return info.num_frames * info.channels * (info.bits_per_sample / 8);
}

/// Get the file extension for a given audio format.
inline std::string default_extension() {
    return ".wav";
}

/// Check if a file path has a WAV extension.
bool is_wav_file(const std::string& filepath);

/// Audio format constants
namespace FormatConstants {
    constexpr int PCM_FORMAT = 1;
    constexpr int DEFAULT_SAMPLE_RATE = 44100;
    constexpr int DEFAULT_CHANNELS = 2;
    constexpr int DEFAULT_BITS_PER_SAMPLE = 16;
    constexpr size_t MAX_FRAMES = 192000 * 600; // 10 minutes at 192kHz
}

} // namespace audioformat
