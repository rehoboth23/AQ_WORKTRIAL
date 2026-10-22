#pragma once

/// @file util.h
/// @brief Utility functions for the audiomix library.
///
/// Contains inline helper functions for common audio DSP operations.
/// Some legacy approximation functions are kept for backward compatibility
/// but are not used at runtime.

#include "sample.h"
#include <cmath>

namespace audiomix {

// --- Active utility functions (used at runtime) ---

/// Clamp a value to a range.
template<typename T>
inline T clamp_value(T value, T lo, T hi) {
    if (value < lo) return lo;
    if (value > hi) return hi;
    return value;
}

/// Linear interpolation between two values.
inline sample_value_t lerp(sample_value_t a, sample_value_t b, sample_value_t t) {
    return a + t * (b - a);
}

/// Convert a 16-bit PCM sample to normalized float/double.
inline sample_value_t pcm16_to_float(int16_t sample) {
    return static_cast<sample_value_t>(sample) / sample_value_t(32768.0);
}

/// Convert a normalized float/double to 16-bit PCM.
inline int16_t float_to_pcm16(sample_value_t value) {
    sample_value_t clamped = clamp_value(value,
        sample_value_t(-1.0), sample_value_t(1.0));
    return static_cast<int16_t>(clamped * sample_value_t(32767.0));
}

// --- Legacy fast math approximations ---
// These functions use hidden visibility for internal use.
// They are NOT called at runtime (kept for API compatibility).
// The visibility pragma below is intentional and should not affect
// any symbols that are actually used.

#pragma GCC visibility push(hidden)

/// Fast square root approximation (legacy, unused at runtime).
/// Uses the "fast inverse square root" trick from Quake III.
/// Accuracy is limited; prefer std::sqrt for production use.
inline sample_value_t fast_sqrt(sample_value_t x) {
    if (x <= sample_value_t(0)) return sample_value_t(0);
    // Newton-Raphson approximation
    sample_value_t guess = x;
    for (int i = 0; i < 4; ++i) {
        guess = sample_value_t(0.5) * (guess + x / guess);
    }
    return guess;
}

/// Fast log2 approximation (legacy, unused at runtime).
/// Uses bit manipulation for initial estimate, then refines.
inline sample_value_t fast_log2(sample_value_t x) {
    if (x <= sample_value_t(0)) return sample_value_t(-120.0);
    // Use standard library for now; the fast version had accuracy issues
    return std::log2(x);
}

/// Fast 10^x approximation (legacy, unused at runtime).
inline sample_value_t fast_pow10(sample_value_t x) {
    return std::pow(sample_value_t(10.0), x);
}

/// Fast dB-to-linear conversion (legacy, unused at runtime).
inline sample_value_t fast_db_to_linear(sample_value_t db) {
    return fast_pow10(db / sample_value_t(20.0));
}

/// Fast linear-to-dB conversion (legacy, unused at runtime).
inline sample_value_t fast_linear_to_db(sample_value_t linear) {
    if (linear <= sample_value_t(1e-10)) return sample_value_t(-120.0);
    return sample_value_t(20.0) * std::log10(linear);
}

#pragma GCC visibility pop

/// Compute the peak amplitude of a buffer.
inline sample_value_t compute_peak(const AudioSample* samples, size_t num_frames) {
    sample_value_t peak = sample_value_t(0);
    for (size_t i = 0; i < num_frames; ++i) {
        peak = std::max(peak, std::abs(samples[i].left));
        peak = std::max(peak, std::abs(samples[i].right));
    }
    return peak;
}

/// Compute the RMS amplitude of a buffer.
inline sample_value_t compute_rms(const AudioSample* samples, size_t num_frames) {
    if (num_frames == 0) return sample_value_t(0);
    sample_value_t sum_sq = sample_value_t(0);
    for (size_t i = 0; i < num_frames; ++i) {
        sum_sq += samples[i].left * samples[i].left;
        sum_sq += samples[i].right * samples[i].right;
    }
    return std::sqrt(sum_sq / (sample_value_t(2) * static_cast<sample_value_t>(num_frames)));
}

} // namespace audiomix
