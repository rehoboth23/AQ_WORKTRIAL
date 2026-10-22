#pragma once

/// @file analyze.h
/// @brief Audio analysis functions for the audiomix library.
///
/// Provides functions for computing RMS levels, peak levels, and
/// clipping detection on audio files. The analysis results are
/// returned as a formatted string suitable for display.

#include <cstddef>

/// Analyze an audio file and compute per-channel metrics.
///
/// Reads the WAV file at the given path, computes RMS and peak levels
/// for each channel, and detects clipping. Results are written to the
/// provided result buffer.
///
/// @param filepath Path to the WAV file to analyze
/// @param result Buffer to receive the formatted result string
/// @param result_size Size of the result buffer in bytes
/// @return 0 on success, -1 on error
///
/// Output format:
///   rms_left=X rms_right=X peak_left=X peak_right=X clipping=X clip_count=X
///
/// Where X values are in dBFS (or "-inf" for silence).
#if defined(AUDIOMIX_BUILDING)
extern "C" __attribute__((visibility("default")))
int audiomix_analyze_file(const char* filepath, char* result, size_t result_size);
#else
extern "C" int audiomix_analyze_file(const char* filepath, char* result, size_t result_size);
#endif
