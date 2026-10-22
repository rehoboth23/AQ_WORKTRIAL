#pragma once

/// @file runner.h
/// @brief Audio processing pipeline runner.
///
/// The PipelineRunner orchestrates the audio processing workflow:
/// reading input, creating processors, running the processing chain,
/// and writing output. It handles the interaction between the
/// audioformat I/O layer and the audiomix processing layer.

#include "audiomix/processor.h"
#include "audiomix/pipeline.h"
#include "audiomix/api.h"
#include <string>
#include <memory>

namespace audioformat {

/// Orchestrates the audio processing pipeline.
///
/// The runner reads a WAV file, creates the requested processor through
/// the audiomix C API, validates the processor type, and runs the
/// processing chain on the audio buffer. The processed audio is then
/// written to the output file.
class PipelineRunner {
public:
    PipelineRunner();
    ~PipelineRunner();

    /// Run the processing pipeline.
    /// @param input_file Path to the input WAV file
    /// @param output_file Path to the output WAV file
    /// @param processor_type Type of processor to use
    /// @param param Processor parameter value
    /// @return 0 on success, non-zero on failure
    int run(const std::string& input_file,
            const std::string& output_file,
            const std::string& processor_type,
            double param);

    /// Get the last error message.
    const std::string& last_error() const { return last_error_; }

private:
    audiomix::ProcessorChain chain_;
    std::string last_error_;

    /// Validate and configure a processor based on its type.
    /// Uses dynamic_cast to verify the processor was created with
    /// the correct derived type, then applies type-specific configuration.
    ///
    /// @param base_proc The base processor pointer from audiomix_init_processor
    /// @param type The requested processor type name
    /// @return The validated processor pointer (may differ from base_proc),
    ///         or nullptr if the type validation failed
    audiomix::AudioProcessor* validateProcessorType(
        audiomix::AudioProcessor* base_proc,
        const std::string& type);
};

} // namespace audioformat
