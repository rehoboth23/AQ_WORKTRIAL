#pragma once

/// @file wav_writer.h
/// @brief WAV file writer for the audioformat library.
///
/// Writes AudioSample buffers as 16-bit PCM WAV files.

#include "audiomix/sample.h"
#include <string>
#include <cstdio>
#include <cstddef>

namespace audioformat {

/// WAV file writer.
///
/// Creates WAV files from AudioSample buffers. Supports 16-bit PCM
/// format with configurable sample rate and channel count.
class WavWriter {
public:
    WavWriter();
    ~WavWriter();

    /// Open a WAV file for writing.
    /// @param filepath Output file path
    /// @param sample_rate Sample rate in Hz
    /// @param channels Number of channels (1 or 2)
    /// @param bits_per_sample Bits per sample (must be 16)
    void open(const std::string& filepath, int sample_rate, int channels,
              int bits_per_sample = 16);

    /// Write audio samples to the file.
    /// @param buffer Source buffer containing AudioSample values
    /// @param num_frames Number of frames to write
    /// @return Number of frames actually written
    size_t write_samples(void* buffer, size_t num_frames);

    /// Close the file and write the final header.
    void close();

    /// Check if the file is open.
    bool is_open() const { return file_ != nullptr; }

private:
    FILE* file_ = nullptr;
    int sample_rate_ = 44100;
    int channels_ = 2;
    int bits_per_sample_ = 16;
    size_t data_size_ = 0;
    size_t data_offset_ = 0;

    void write_header();
    void update_header();
};

} // namespace audioformat
