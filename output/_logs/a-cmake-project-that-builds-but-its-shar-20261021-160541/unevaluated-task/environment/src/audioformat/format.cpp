#include "format.h"

#include <algorithm>
#include <stdexcept>

namespace audioformat {

std::string format_description(const audiomix::AudioBufferInfo& info)
{
    std::string format_name = (info.audio_format == 1) ? "PCM" : "Unknown";
    return format_name + " " + std::to_string(info.bits_per_sample) + "-bit " +
           std::to_string(info.channels) + "ch " +
           std::to_string(info.sample_rate) + "Hz " +
           std::to_string(info.num_frames) + " frames";
}

bool validate_format(const audiomix::AudioBufferInfo& info)
{
    if (info.audio_format != FormatConstants::PCM_FORMAT) {
        return false;
    }
    if (info.channels < 1 || info.channels > 2) {
        return false;
    }
    if (info.sample_rate <= 0 || info.sample_rate > 192000) {
        return false;
    }
    if (info.bits_per_sample != 16) {
        return false;
    }
    if (info.num_frames == 0 || info.num_frames > FormatConstants::MAX_FRAMES) {
        return false;
    }
    return true;
}

bool is_wav_file(const std::string& filepath)
{
    if (filepath.length() < 4) return false;
    std::string ext = filepath.substr(filepath.length() - 4);
    // Case-insensitive comparison
    std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
    return ext == ".wav";
}

} // namespace audioformat
