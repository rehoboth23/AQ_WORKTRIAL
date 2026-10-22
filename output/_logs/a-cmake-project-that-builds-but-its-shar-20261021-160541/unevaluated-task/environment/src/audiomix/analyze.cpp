#include "analyze.h"
#include "sample.h"
#include "util.h"

#include <cstdio>
#include <cstring>
#include <cmath>
#include <vector>
#include <string>

/// Simple WAV file reader for analysis.
/// This is a minimal implementation that handles 16-bit PCM WAV files.
/// It does not depend on the audioformat library, keeping the analysis
/// module self-contained.

namespace {

struct WavInfo {
    uint16_t audio_format;
    uint16_t channels;
    uint32_t sample_rate;
    uint16_t bits_per_sample;
    uint32_t data_size;
};

bool read_wav_header(FILE* f, WavInfo& info) {
    char riff_tag[4];
    if (fread(riff_tag, 1, 4, f) != 4) return false;
    if (memcmp(riff_tag, "RIFF", 4) != 0) return false;

    uint32_t file_size;
    if (fread(&file_size, 4, 1, f) != 1) return false;

    char wave_tag[4];
    if (fread(wave_tag, 1, 4, f) != 4) return false;
    if (memcmp(wave_tag, "WAVE", 4) != 0) return false;

    // Reset info
    info.audio_format = 0;
    info.channels = 0;
    info.sample_rate = 0;
    info.bits_per_sample = 0;
    info.data_size = 0;

    bool found_fmt = false;
    bool found_data = false;

    while (!found_data && !feof(f)) {
        char chunk_id[4];
        uint32_t chunk_size;

        if (fread(chunk_id, 1, 4, f) != 4) break;
        if (fread(&chunk_size, 4, 1, f) != 1) break;

        if (memcmp(chunk_id, "fmt ", 4) == 0) {
            found_fmt = true;
            size_t to_read = chunk_size;
            if (to_read >= 16) {
                uint16_t fmt_data[8]; // enough for first 16 bytes
                size_t read_bytes = (to_read < sizeof(fmt_data)) ? to_read : 16;
                if (fread(fmt_data, 1, read_bytes, f) != read_bytes) return false;
                info.audio_format = fmt_data[0];
                info.channels = fmt_data[1];
                info.sample_rate = *(uint32_t*)&fmt_data[2];
                info.bits_per_sample = fmt_data[6];
                if (to_read > read_bytes) {
                    fseek(f, to_read - read_bytes, SEEK_CUR);
                }
            } else {
                fseek(f, to_read, SEEK_CUR);
            }
        } else if (memcmp(chunk_id, "data", 4) == 0) {
            found_data = true;
            info.data_size = chunk_size;
            // Don't seek past data - we'll read it next
        } else {
            // Skip unknown chunk
            fseek(f, chunk_size, SEEK_CUR);
        }
    }

    return found_fmt && found_data;
}

std::string format_db_value(double value_db) {
    if (value_db <= -120.0) {
        return "-inf";
    }
    char buf[32];
    snprintf(buf, sizeof(buf), "%.2f", value_db);
    return std::string(buf);
}

} // anonymous namespace

int audiomix_analyze_file(const char* filepath, char* result, size_t result_size)
{
    if (!filepath || !result || result_size == 0) {
        return -1;
    }

    FILE* f = fopen(filepath, "rb");
    if (!f) {
        return -1;
    }

    WavInfo wav_info;
    if (!read_wav_header(f, wav_info)) {
        fclose(f);
        return -1;
    }

    // Only support 16-bit PCM for simplicity
    if (wav_info.audio_format != 1 || wav_info.bits_per_sample != 16) {
        fclose(f);
        return -1;
    }

    // Read PCM data
    size_t total_samples = wav_info.data_size / 2; // 16-bit = 2 bytes per sample
    std::vector<int16_t> pcm_data(total_samples);
    size_t samples_read = fread(pcm_data.data(), 2, total_samples, f);
    fclose(f);

    if (samples_read == 0) {
        pcm_data.clear();
    }

    size_t num_frames = samples_read / wav_info.channels;
    if (num_frames == 0) {
        // Empty file
        snprintf(result, result_size,
                 "rms_left=-inf rms_right=-inf peak_left=-inf peak_right=-inf clipping=0 clip_count=0");
        return 0;
    }

    // Compute per-channel RMS, peak, and clipping
    double rms_left = 0.0, rms_right = 0.0;
    double peak_left = 0.0, peak_right = 0.0;
    int clip_count = 0;

    for (size_t i = 0; i < num_frames; ++i) {
        double left = static_cast<double>(pcm_data[i * wav_info.channels]) / 32768.0;
        double right = (wav_info.channels > 1)
            ? static_cast<double>(pcm_data[i * wav_info.channels + 1]) / 32768.0
            : left;

        rms_left += left * left;
        rms_right += right * right;
        peak_left = std::max(peak_left, std::abs(left));
        peak_right = std::max(peak_right, std::abs(right));

        // Clipping: sample value at or very near the maximum
        if (std::abs(pcm_data[i * wav_info.channels]) >= 32767) {
            clip_count++;
        } else if (wav_info.channels > 1 &&
                   std::abs(pcm_data[i * wav_info.channels + 1]) >= 32767) {
            clip_count++;
        }
    }

    // Finalize RMS
    rms_left = std::sqrt(rms_left / num_frames);
    rms_right = std::sqrt(rms_right / num_frames);

    // Convert to dB
    double rms_left_db = (rms_left > 0) ? 20.0 * std::log10(rms_left) : -120.0;
    double rms_right_db = (rms_right > 0) ? 20.0 * std::log10(rms_right) : -120.0;
    double peak_left_db = (peak_left > 0) ? 20.0 * std::log10(peak_left) : -120.0;
    double peak_right_db = (peak_right > 0) ? 20.0 * std::log10(peak_right) : -120.0;

    // Map -120 dB (our floor) to -inf for display
    int clipping = (clip_count > 0) ? 1 : 0;

    std::string out = "rms_left=" + format_db_value(rms_left_db) +
                      " rms_right=" + format_db_value(rms_right_db) +
                      " peak_left=" + format_db_value(peak_left_db) +
                      " peak_right=" + format_db_value(peak_right_db) +
                      " clipping=" + std::to_string(clipping) +
                      " clip_count=" + std::to_string(clip_count);

    snprintf(result, result_size, "%s", out.c_str());
    return 0;
}
