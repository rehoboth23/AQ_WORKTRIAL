#pragma once

/// @file wav_reader.h
/// @brief WAV file reader for the audioformat library.
///
/// Reads 16-bit PCM WAV files and converts samples to the internal
/// AudioSample format used by the processing pipeline.

#include "audiomix/sample.h"
#include <string>
#include <cstdio>
#include <vector>
#include <cstddef>

namespace audioformat {

/// WAV file reader.
///
/// Opens and reads WAV files, converting the raw PCM data into
/// AudioSample buffers suitable for processing. Supports 16-bit
/// PCM format only.
class WavReader {
public:
    WavReader();
    ~WavReader();

    /// Open a WAV file for reading.
    /// @param filepath Path to the WAV file
    /// @return AudioBufferInfo with format metadata, or throws on error
    audiomix::AudioBufferInfo open(const std::string& filepath);

    /// Read audio samples into the provided buffer.
    /// The buffer must be large enough for num_frames AudioSample values.
    /// @param buffer Destination buffer (allocated via audiomix_init_buffer)
    /// @param num_frames Number of frames to read
    /// @return Number of frames actually read
    size_t read_samples(void* buffer, size_t num_frames);

    /// Read all remaining samples from the file.
    /// @param buffer Destination buffer
    /// @return Number of frames read
    size_t read_all(void* buffer);

    /// Close the file.
    void close();

    /// Get the audio format info.
    const audiomix::AudioBufferInfo& info() const { return info_; }

    /// Check if the file is open.
    bool is_open() const { return file_ != nullptr; }

private:
    FILE* file_ = nullptr;
    audiomix::AudioBufferInfo info_ = {};
    size_t frames_remaining_ = 0;

    bool parse_header();
    bool find_chunk(const char* target_id, uint32_t& chunk_size);
};

} // namespace audioformat
