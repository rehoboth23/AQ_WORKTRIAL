#include "runner.h"
#include "wav_reader.h"
#include "wav_writer.h"
#include "format.h"

#include <stdexcept>
#include <cstring>

namespace audioformat {

PipelineRunner::PipelineRunner()
{
}

PipelineRunner::~PipelineRunner()
{
    chain_.clear();
}

audiomix::AudioProcessor* PipelineRunner::validateProcessorType(
    audiomix::AudioProcessor* base_proc,
    const std::string& type)
{
    if (!base_proc) return nullptr;

    // Use dynamic_cast to verify the processor was created with the
    // correct derived type. This is important for cross-library
    // type safety: if the audiomix library's typeinfo is not visible
    // to us, the cast will fail and return nullptr.
    if (type == "normalize") {
        return dynamic_cast<audiomix::NormalizationProcessor*>(base_proc);
    } else if (type == "gain") {
        return dynamic_cast<audiomix::GainProcessor*>(base_proc);
    } else if (type == "limiter") {
        return dynamic_cast<audiomix::LimiterProcessor*>(base_proc);
    } else if (type == "compressor") {
        return dynamic_cast<audiomix::CompressorProcessor*>(base_proc);
    }

    // Unknown type: return the base pointer as-is
    return base_proc;
}

int PipelineRunner::run(const std::string& input_file,
                        const std::string& output_file,
                        const std::string& processor_type,
                        double param)
{
    last_error_.clear();
    chain_.clear();

    try {
        // Step 1: Read input WAV file
        WavReader reader;
        audiomix::AudioBufferInfo info = reader.open(input_file);

        if (!validate_format(info)) {
            last_error_ = "Unsupported audio format in input file";
            return 1;
        }

        // Step 2: Allocate processing buffer via audiomix API
        // This ensures the buffer is properly sized and aligned for
        // the library's internal AudioSample representation.
        void* buffer = audiomix_init_buffer(info.num_frames);
        if (!buffer) {
            last_error_ = "Failed to allocate processing buffer";
            return 1;
        }

        // Step 3: Read audio samples into the buffer
        size_t frames_read = reader.read_all(buffer);
        reader.close();

        if (frames_read != info.num_frames) {
            // Partial read - still process what we have
        }

        // Step 4: Create the requested processor via C API
        void* raw_proc = audiomix_init_processor(processor_type.c_str(), param);
        if (!raw_proc) {
            audiomix_free_buffer(buffer);
            last_error_ = "Failed to create processor: " + processor_type;
            return 1;
        }

        audiomix::AudioProcessor* base_proc =
            static_cast<audiomix::AudioProcessor*>(raw_proc);

        // Step 5: Validate the processor type using RTTI
        // This performs a dynamic_cast to verify the processor's
        // actual derived type matches what we requested.
        audiomix::AudioProcessor* validated_proc =
            validateProcessorType(base_proc, processor_type);

        // Step 6: Add the processor to the chain and run
        chain_.addProcessor(validated_proc);
        chain_.run(static_cast<AudioSample*>(buffer), info.num_frames);

        // Step 7: Write the processed audio to output file
        WavWriter writer;
        writer.open(output_file, info.sample_rate, info.channels,
                    info.bits_per_sample);
        writer.write_samples(buffer, info.num_frames);
        writer.close();

        // Step 8: Cleanup
        chain_.clear();
        audiomix_free_processor(raw_proc);
        audiomix_free_buffer(buffer);

        return 0;

    } catch (const std::exception& e) {
        last_error_ = e.what();
        return 1;
    }
}

} // namespace audioformat
