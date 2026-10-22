#include "wav_reader.h"

#include <cstring>
#include <stdexcept>
#include <algorithm>

namespace audioformat {

WavReader::WavReader()
    : file_(nullptr)
{
}

WavReader::~WavReader()
{
    close();
}

bool WavReader::find_chunk(const char* target_id, uint32_t& chunk_size)
{
    while (!feof(file_)) {
        char chunk_id[4];
        if (fread(chunk_id, 1, 4, file_) != 4) return false;

        uint32_t size;
        if (fread(&size, 4, 1, file_) != 1) return false;

        if (memcmp(chunk_id, target_id, 4) == 0) {
            chunk_size = size;
            return true;
        }

        // Skip this chunk
        fseek(file_, size, SEEK_CUR);
    }
    return false;
}

bool WavReader::parse_header()
{
    // Read RIFF header
    char riff_tag[4];
    if (fread(riff_tag, 1, 4, file_) != 4) return false;
    if (memcmp(riff_tag, "RIFF", 4) != 0) return false;

    uint32_t file_size;
    if (fread(&file_size, 4, 1, file_) != 1) return false;

    char wave_tag[4];
    if (fread(wave_tag, 1, 4, file_) != 4) return false;
    if (memcmp(wave_tag, "WAVE", 4) != 0) return false;

    // Find fmt chunk
    uint32_t fmt_size;
    if (!find_chunk("fmt ", fmt_size)) return false;

    // Parse fmt chunk
    uint16_t audio_format = 0;
    uint16_t channels = 0;
    uint32_t sample_rate = 0;
    uint32_t byte_rate = 0;
    uint16_t block_align = 0;
    uint16_t bits_per_sample = 0;

    if (fread(&audio_format, 2, 1, file_) != 1) return false;
    if (fread(&channels, 2, 1, file_) != 1) return false;
    if (fread(&sample_rate, 4, 1, file_) != 1) return false;
    if (fread(&byte_rate, 4, 1, file_) != 1) return false;
    if (fread(&block_align, 2, 1, file_) != 1) return false;
    if (fread(&bits_per_sample, 2, 1, file_) != 1) return false;

    // Skip any extra fmt data
    if (fmt_size > 16) {
        fseek(file_, fmt_size - 16, SEEK_CUR);
    }

    // Validate format
    if (audio_format != 1) {
        // Not PCM - unsupported
        return false;
    }
    if (bits_per_sample != 16) {
        // Not 16-bit - unsupported
        return false;
    }
    if (channels < 1 || channels > 2) {
        // Only mono or stereo supported
        return false;
    }

    // Find data chunk
    uint32_t data_size;
    if (!find_chunk("data", data_size)) return false;

    // Fill info structure
    info_.audio_format = audio_format;
    info_.channels = channels;
    info_.sample_rate = sample_rate;
    info_.bits_per_sample = bits_per_sample;
    info_.num_frames = data_size / (channels * (bits_per_sample / 8));
    frames_remaining_ = info_.num_frames;

    return true;
}

audiomix::AudioBufferInfo WavReader::open(const std::string& filepath)
{
    close();

    file_ = fopen(filepath.c_str(), "rb");
    if (!file_) {
        throw std::runtime_error("Cannot open WAV file: " + filepath);
    }

    if (!parse_header()) {
        close();
        throw std::runtime_error("Invalid WAV file format: " + filepath);
    }

    return info_;
}

size_t WavReader::read_samples(void* buffer, size_t num_frames)
{
    if (!file_ || !buffer || num_frames == 0) return 0;

    AudioSample* samples = static_cast<AudioSample*>(buffer);
    size_t frames_to_read = std::min(num_frames, frames_remaining_);

    for (size_t i = 0; i < frames_to_read; ++i) {
        int16_t pcm[2] = {0, 0};

        // Read raw PCM samples
        size_t samples_to_read = info_.channels;
        if (fread(pcm, 2, samples_to_read, file_) != samples_to_read) {
            frames_remaining_ = 0;
            return i;
        }

        // Convert to AudioSample format
        samples[i].left = audiomix::pcm16_to_float(pcm[0]);
        samples[i].right = (info_.channels > 1)
            ? audiomix::pcm16_to_float(pcm[1])
            : samples[i].left;
    }

    frames_remaining_ -= frames_to_read;
    return frames_to_read;
}

size_t WavReader::read_all(void* buffer)
{
    if (!file_ || !buffer) return 0;
    return read_samples(buffer, frames_remaining_);
}

void WavReader::close()
{
    if (file_) {
        fclose(file_);
        file_ = nullptr;
    }
    frames_remaining_ = 0;
}

} // namespace audioformat
