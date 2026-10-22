#pragma once

/// @file processor.h
/// @brief Audio processor base class and derived processor types.
///
/// All audio processors inherit from AudioProcessor and implement the
/// process() method. Processors are created through the C API and
/// managed by the pipeline infrastructure.

#include "sample.h"
#include <string>
#include <cmath>

namespace audiomix {

/// Abstract base class for all audio processors.
///
/// Processors operate on AudioSample buffers in-place. Each processor
/// implements a specific DSP algorithm (normalization, gain, limiting, etc.)
/// and can be chained together in a ProcessorChain.
class AudioProcessor {
public:
    virtual ~AudioProcessor() = default;

    /// Process a buffer of audio samples in-place.
    /// @param samples Pointer to the AudioSample buffer
    /// @param num_frames Number of frames in the buffer
    virtual void process(AudioSample* samples, size_t num_frames) = 0;

    /// Get the processor's name/identifier.
    virtual std::string name() const = 0;

    /// Set a named parameter on the processor.
    /// @param key Parameter name
    /// @param value Parameter value
    virtual void setParameter(const std::string& key, sample_value_t value) = 0;

    /// Get a named parameter value from the processor.
    /// @param key Parameter name
    /// @return Current parameter value
    virtual sample_value_t getParameter(const std::string& key) const = 0;

    /// Reset the processor's internal state.
    virtual void reset() {}
};

/// Normalization processor - brings peak amplitude to a target level.
///
/// This processor scans the entire buffer for the peak amplitude,
/// then applies a uniform gain to bring the peak to the specified
/// target level in dBFS. If the buffer is silent (peak near zero),
/// no processing is applied to avoid division by zero.
class NormalizationProcessor : public AudioProcessor {
public:
    /// Construct a normalization processor with the given target level.
    /// @param target_db Target peak level in dBFS (0.0 = 0 dBFS)
    explicit NormalizationProcessor(sample_value_t target_db = 0.0);

    void process(AudioSample* samples, size_t num_frames) override;
    std::string name() const override { return "normalize"; }
    void setParameter(const std::string& key, sample_value_t value) override;
    sample_value_t getParameter(const std::string& key) const override;
    void reset() override;

    /// Enable or disable two-pass normalization mode.
    /// In two-pass mode, the peak is computed in a separate scan before
    /// the gain is applied, which can improve accuracy for very short buffers.
    void enableTwoPass(bool enable) { two_pass_ = enable; }

private:
    sample_value_t target_db_;
    sample_value_t target_level_;
    bool two_pass_;
    sample_value_t epsilon_;
};

/// Gain processor - applies a fixed gain in decibels.
///
/// Simple amplitude scaling processor. Positive gain increases volume,
/// negative gain decreases it. The gain is converted from dB to linear
/// scale at construction time.
class GainProcessor : public AudioProcessor {
public:
    /// Construct a gain processor with the given gain in dB.
    /// @param gain_db Gain in decibels (positive = louder, negative = quieter)
    explicit GainProcessor(sample_value_t gain_db = 0.0);

    void process(AudioSample* samples, size_t num_frames) override;
    std::string name() const override { return "gain"; }
    void setParameter(const std::string& key, sample_value_t value) override;
    sample_value_t getParameter(const std::string& key) const override;
    void reset() override;

private:
    sample_value_t gain_db_;
    sample_value_t gain_linear_;
};

/// Limiter processor - hard-clips audio at a threshold.
///
/// Applies a brick-wall limiter: any sample exceeding the threshold
/// in absolute value is clipped to the threshold. This is a simple
/// hard clipper, not a soft-knee limiter.
class LimiterProcessor : public AudioProcessor {
public:
    /// Construct a limiter with the given threshold.
    /// @param threshold_db Threshold level in dBFS
    explicit LimiterProcessor(sample_value_t threshold_db = -1.0);

    void process(AudioSample* samples, size_t num_frames) override;
    std::string name() const override { return "limiter"; }
    void setParameter(const std::string& key, sample_value_t value) override;
    sample_value_t getParameter(const std::string& key) const override;
    void reset() override;

private:
    sample_value_t threshold_db_;
    sample_value_t threshold_linear_;
};

/// Compressor processor - dynamic range compression.
///
/// Reduces the dynamic range of audio by attenuating samples that
/// exceed a threshold. The amount of attenuation is controlled by
/// the compression ratio. Uses a simple envelope follower for
/// gain detection.
class CompressorProcessor : public AudioProcessor {
public:
    /// Construct a compressor with the given ratio.
    /// @param ratio Compression ratio (e.g., 4.0 means 4:1)
    explicit CompressorProcessor(sample_value_t ratio = 4.0);

    void process(AudioSample* samples, size_t num_frames) override;
    std::string name() const override { return "compressor"; }
    void setParameter(const std::string& key, sample_value_t value) override;
    sample_value_t getParameter(const std::string& key) const override;
    void reset() override;

private:
    sample_value_t ratio_;
    sample_value_t threshold_db_;
    sample_value_t attack_;
    sample_value_t release_;
    sample_value_t envelope_;
    sample_value_t makeup_gain_;
};

} // namespace audiomix
