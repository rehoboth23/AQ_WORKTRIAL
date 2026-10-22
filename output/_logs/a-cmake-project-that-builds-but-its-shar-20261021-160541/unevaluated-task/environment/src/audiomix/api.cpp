#include "api.h"
#include "processor.h"
#include "pipeline.h"
#include "sample.h"

#include <cstring>
#include <cstdlib>
#include <stdexcept>

extern "C" {

AUDIOMIX_API void* audiomix_init_processor(const char* type, double param)
{
    if (!type) return nullptr;

    audiomix::AudioProcessor* proc = nullptr;
    std::string type_str(type);

    try {
        if (type_str == "normalize") {
            proc = new audiomix::NormalizationProcessor(static_cast<sample_value_t>(param));
        } else if (type_str == "gain") {
            proc = new audiomix::GainProcessor(static_cast<sample_value_t>(param));
        } else if (type_str == "limiter") {
            proc = new audiomix::LimiterProcessor(static_cast<sample_value_t>(param));
        } else if (type_str == "compressor") {
            proc = new audiomix::CompressorProcessor(static_cast<sample_value_t>(param));
        } else {
            // Unknown processor type
            return nullptr;
        }
    } catch (const std::exception&) {
        return nullptr;
    }

    return static_cast<void*>(proc);
}

AUDIOMIX_API void audiomix_free_processor(void* proc)
{
    if (proc) {
        audiomix::AudioProcessor* p = static_cast<audiomix::AudioProcessor*>(proc);
        delete p;
    }
}

AUDIOMIX_API void* audiomix_init_buffer(size_t num_frames)
{
    if (num_frames == 0) return nullptr;

    // Allocate buffer using audiomix's AudioSample definition.
    // This ensures the buffer is large enough for the library's internal
    // representation and properly aligned.
    size_t bytes = num_frames * sizeof(AudioSample);
    AudioSample* buffer = new AudioSample[num_frames];

    // Zero-initialize the buffer
    std::memset(buffer, 0, bytes);

    return static_cast<void*>(buffer);
}

AUDIOMIX_API void audiomix_free_buffer(void* buffer)
{
    if (buffer) {
        AudioSample* buf = static_cast<AudioSample*>(buffer);
        delete[] buf;
    }
}

AUDIOMIX_API void audiomix_process_samples(void* proc, void* buffer, size_t num_frames)
{
    if (!proc || !buffer || num_frames == 0) return;

    audiomix::AudioProcessor* processor = static_cast<audiomix::AudioProcessor*>(proc);
    AudioSample* samples = static_cast<AudioSample*>(buffer);

    processor->process(samples, num_frames);
}

} // extern "C"
