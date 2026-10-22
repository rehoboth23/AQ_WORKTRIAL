#pragma once

/// @file pipeline.h
/// @brief Processor chain and pipeline configuration for the audiomix library.
///
/// The ProcessorChain holds an ordered sequence of AudioProcessor pointers
/// and runs them in sequence on an audio buffer. The PipelineConfig holds
/// metadata about the audio format being processed.

#include "processor.h"
#include <vector>
#include <string>
#include <memory>
#include <mutex>

namespace audiomix {

/// Ordered chain of audio processors that are run in sequence.
///
/// The chain does not own the processor pointers; the caller is responsible
/// for managing the lifetime of the processors. Processors are run in the
/// order they are added.
class ProcessorChain {
public:
    ProcessorChain() = default;
    ~ProcessorChain();

    // Non-copyable
    ProcessorChain(const ProcessorChain&) = delete;
    ProcessorChain& operator=(const ProcessorChain&) = delete;

    // Movable
    ProcessorChain(ProcessorChain&&) = default;
    ProcessorChain& operator=(ProcessorChain&&) = default;

    /// Add a processor to the end of the chain.
    /// @param proc Pointer to the processor to add
    void addProcessor(AudioProcessor* proc);

    /// Remove a processor from the chain.
    /// @param proc Pointer to the processor to remove
    void removeProcessor(AudioProcessor* proc);

    /// Remove all processors from the chain.
    void clear();

    /// Get the number of processors in the chain.
    size_t size() const { return processors_.size(); }

    /// Check if the chain is empty.
    bool empty() const { return processors_.empty(); }

    /// Run all processors in sequence on the given buffer.
    /// @param samples Audio buffer to process (modified in-place)
    /// @param num_frames Number of frames in the buffer
    void run(AudioSample* samples, size_t num_frames);

    /// Get a processor by index.
    /// @param index Zero-based index of the processor
    /// @return Pointer to the processor, or nullptr if index is out of range
    AudioProcessor* getProcessor(size_t index) const;

    /// Get the processor list (for iteration).
    const std::vector<AudioProcessor*>& processors() const { return processors_; }

private:
    std::vector<AudioProcessor*> processors_;
};

/// Configuration for an audio processing pipeline.
///
/// Stores metadata about the audio format (sample rate, channels, etc.)
/// that processors may need to configure themselves correctly.
class PipelineConfig {
public:
    PipelineConfig() = default;

    void setSampleRate(int sr) { sample_rate_ = sr; }
    int sampleRate() const { return sample_rate_; }

    void setChannels(int ch) { channels_ = ch; }
    int channels() const { return channels_; }

    void setNumFrames(size_t n) { num_frames_ = n; }
    size_t numFrames() const { return num_frames_; }

    void setBitsPerSample(int bps) { bits_per_sample_ = bps; }
    int bitsPerSample() const { return bits_per_sample_; }

    /// Compute the total buffer size in bytes for AudioSample format.
    size_t bufferSizeBytes() const {
        return num_frames_ * sizeof(AudioSample);
    }

private:
    int sample_rate_ = 44100;
    int channels_ = 2;
    size_t num_frames_ = 0;
    int bits_per_sample_ = 16;
};

} // namespace audiomix
