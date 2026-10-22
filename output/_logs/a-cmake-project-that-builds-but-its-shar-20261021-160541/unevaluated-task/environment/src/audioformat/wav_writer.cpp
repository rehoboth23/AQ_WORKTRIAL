#include "wav_writer.h"
#include "audiomix/util.h"

#include <cstring>
#include <stdexcept>

namespace audioformat {

WavWriter::WavWriter()
    : file_(nullptr)
{
}

WavWriter::~WavWriter()
{
    close();
}

void WavWriter::write_header()
{
    // RIFF header
    uint32_t riff_size = 36 + data_size_; // Will be updated on close
    fwrite("RIFF", 1, 4, file_);
    fwrite(&riff_size, 4, 1, file_);
    fwrite("WAVE", 1, 4, file_);

    // fmt chunk
    uint32_t fmt_size = 16;
    uint16_t audio_format = 1; // PCM
    uint16_t channels = static_cast<uint16_t>(channels_);
    uint32_t sample_rate = static_cast<uint32_t>(sample_rate_);
    uint16_t block_align = static_cast<uint16_t>(channels_ * bits_per_sample_ / 8);
    uint32_t byte_rate = sample_rate_ * block_align;
    uint16_t bits_per_sample = static_cast<uint16_t>(bits_per_sample_);

    fwrite("fmt ", 1, 4, file_);
    fwrite(&fmt_size, 4, 1, file_);
    fwrite(&audio_format, 2, 1, file_);
    fwrite(&channels, 2, 1, file_);
    fwrite(&sample_rate, 4, 1, file_);
    fwrite(&byte_rate, 4, 1, file_);
    fwrite(&block_align, 2, 1, file_);
    fwrite(&bits_per_sample, 2, 1, file_);

    // data chunk header (size will be updated on close)
    data_offset_ = ftell(file_) + 4;
    fwrite("data", 1, 4, file_);
    fwrite(&data_size_, 4, 1, file_);
}

void WavWriter::update_header()
{
    if (!file_) return;

    // Update RIFF size
    long riff_size_pos = 4;
    fseek(file_, riff_size_pos, SEEK_SET);
    uint32_t riff_size = 36 + data_size_;
    fwrite(&riff_size, 4, 1, file_);

    // Update data chunk size
    fseek(file_, static_cast<long>(data_offset_), SEEK_SET);
    fwrite(&data_size_, 4, 1, file_);

    // Seek to end
    fseek(file_, 0, SEEK_END);
}

void WavWriter::open(const std::string& filepath, int sample_rate, int channels,
                      int bits_per_sample)
{
    close();

    if (bits_per_sample != 16) {
        throw std::runtime_error("Only 16-bit PCM WAV is supported");
    }
    if (channels < 1 || channels > 2) {
        throw std::runtime_error("Only 1 or 2 channels supported");
    }

    sample_rate_ = sample_rate;
    channels_ = channels;
    bits_per_sample_ = bits_per_sample;
    data_size_ = 0;

    file_ = fopen(filepath.c_str(), "wb");
    if (!file_) {
        throw std::runtime_error("Cannot create WAV file: " + filepath);
    }

    write_header();
}

size_t WavWriter::write_samples(void* buffer, size_t num_frames)
{
    if (!file_ || !buffer || num_frames == 0) return 0;

    AudioSample* samples = static_cast<AudioSample*>(buffer);

    for (size_t i = 0; i < num_frames; ++i) {
        // Convert to 16-bit PCM with clipping
        int16_t left = audiomix::float_to_pcm16(samples[i].left);
        int16_t right = audiomix::float_to_pcm16(samples[i].right);

        fwrite(&left, 2, 1, file_);
        if (channels_ > 1) {
            fwrite(&right, 2, 1, file_);
        }

        data_size_ += channels_ * 2;
    }

    return num_frames;
}

void WavWriter::close()
{
    if (file_) {
        update_header();
        fclose(file_);
        file_ = nullptr;
    }
}

} // namespace audioformat
