#include "processor.h"
#include "util.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <limits>

namespace audiomix {

// ---------------------------------------------------------------------------
// NormalizationProcessor
// ---------------------------------------------------------------------------

NormalizationProcessor::NormalizationProcessor(sample_value_t target_db)
    : target_db_(target_db)
    , target_level_(db_to_linear(target_db))
    , two_pass_(false)
    , epsilon_(AudioConstants::SILENCE_THRESHOLD)
{
}

void NormalizationProcessor::process(AudioSample* samples, size_t num_frames)
{
    if (!samples || num_frames == 0) {
        return;
    }

    // --- Pass 1: Find peak amplitude across all channels ---
    sample_value_t peak = sample_value_t(0);
    for (size_t i = 0; i < num_frames; ++i) {
        sample_value_t abs_left = std::abs(samples[i].left);
        sample_value_t abs_right = std::abs(samples[i].right);
        if (abs_left > peak) peak = abs_left;
        if (abs_right > peak) peak = abs_right;
    }

    // Handle silence: if peak is essentially zero, skip processing
    // to avoid division by zero and NaN propagation
    if (peak < epsilon_) {
        return;
    }

    // --- Compute gain to bring peak to target level ---
    sample_value_t gain = target_level_ / peak;

    // --- Pass 2: Apply gain to all samples ---
    if (two_pass_) {
        // In two-pass mode, compute peak first, then apply gain
        // This is functionally identical but separated for clarity
        for (size_t i = 0; i < num_frames; ++i) {
            samples[i].left *= gain;
            samples[i].right *= gain;
        }
    } else {
        // Single-pass: same computation, just written more compactly
        for (size_t i = 0; i < num_frames; ++i) {
            samples[i].left *= gain;
            samples[i].right *= gain;
        }
    }
}

void NormalizationProcessor::setParameter(const std::string& key, sample_value_t value)
{
    if (key == "target_db") {
        target_db_ = value;
        target_level_ = db_to_linear(target_db_);
    } else if (key == "two_pass") {
        two_pass_ = (value > sample_value_t(0));
    } else if (key == "epsilon") {
        epsilon_ = value;
    }
}

sample_value_t NormalizationProcessor::getParameter(const std::string& key) const
{
    if (key == "target_db") return target_db_;
    if (key == "target_level") return target_level_;
    if (key == "two_pass") return two_pass_ ? sample_value_t(1) : sample_value_t(0);
    if (key == "epsilon") return epsilon_;
    return sample_value_t(0);
}

void NormalizationProcessor::reset()
{
    target_db_ = 0.0;
    target_level_ = db_to_linear(0.0);
    two_pass_ = false;
    epsilon_ = AudioConstants::SILENCE_THRESHOLD;
}

// ---------------------------------------------------------------------------
// GainProcessor
// ---------------------------------------------------------------------------

GainProcessor::GainProcessor(sample_value_t gain_db)
    : gain_db_(gain_db)
    , gain_linear_(db_to_linear(gain_db))
{
}

void GainProcessor::process(AudioSample* samples, size_t num_frames)
{
    if (!samples || num_frames == 0) {
        return;
    }

    // Apply gain to all samples
    for (size_t i = 0; i < num_frames; ++i) {
        samples[i].left *= gain_linear_;
        samples[i].right *= gain_linear_;
    }
}

void GainProcessor::setParameter(const std::string& key, sample_value_t value)
{
    if (key == "gain_db") {
        gain_db_ = value;
        gain_linear_ = db_to_linear(gain_db_);
    } else if (key == "gain_linear") {
        gain_linear_ = value;
        gain_db_ = linear_to_db(gain_linear_);
    }
}

sample_value_t GainProcessor::getParameter(const std::string& key) const
{
    if (key == "gain_db") return gain_db_;
    if (key == "gain_linear") return gain_linear_;
    return sample_value_t(0);
}

void GainProcessor::reset()
{
    gain_db_ = 0.0;
    gain_linear_ = db_to_linear(0.0);
}

// ---------------------------------------------------------------------------
// LimiterProcessor
// ---------------------------------------------------------------------------

LimiterProcessor::LimiterProcessor(sample_value_t threshold_db)
    : threshold_db_(threshold_db)
    , threshold_linear_(db_to_linear(threshold_db))
{
}

void LimiterProcessor::process(AudioSample* samples, size_t num_frames)
{
    if (!samples || num_frames == 0) {
        return;
    }

    // Hard clip samples that exceed the threshold
    for (size_t i = 0; i < num_frames; ++i) {
        // Clip left channel
        if (samples[i].left > threshold_linear_) {
            samples[i].left = threshold_linear_;
        } else if (samples[i].left < -threshold_linear_) {
            samples[i].left = -threshold_linear_;
        }

        // Clip right channel
        if (samples[i].right > threshold_linear_) {
            samples[i].right = threshold_linear_;
        } else if (samples[i].right < -threshold_linear_) {
            samples[i].right = -threshold_linear_;
        }
    }
}

void LimiterProcessor::setParameter(const std::string& key, sample_value_t value)
{
    if (key == "threshold_db") {
        threshold_db_ = value;
        threshold_linear_ = db_to_linear(threshold_db_);
    } else if (key == "threshold_linear") {
        threshold_linear_ = value;
        threshold_db_ = linear_to_db(threshold_linear_);
    }
}

sample_value_t LimiterProcessor::getParameter(const std::string& key) const
{
    if (key == "threshold_db") return threshold_db_;
    if (key == "threshold_linear") return threshold_linear_;
    return sample_value_t(0);
}

void LimiterProcessor::reset()
{
    threshold_db_ = -1.0;
    threshold_linear_ = db_to_linear(-1.0);
}

// ---------------------------------------------------------------------------
// CompressorProcessor
// ---------------------------------------------------------------------------

CompressorProcessor::CompressorProcessor(sample_value_t ratio)
    : ratio_(ratio)
    , threshold_db_(-20.0)
    , attack_(0.01)
    , release_(0.1)
    , envelope_(0.0)
    , makeup_gain_(1.0)
{
}

void CompressorProcessor::process(AudioSample* samples, size_t num_frames)
{
    if (!samples || num_frames == 0) {
        return;
    }

    for (size_t i = 0; i < num_frames; ++i) {
        // Compute input level (peak of left and right)
        sample_value_t input_level = std::max(std::abs(samples[i].left),
                                               std::abs(samples[i].right));

        // Envelope follower with separate attack and release
        if (input_level > envelope_) {
            // Attack: instant (for simplicity, could use exponential attack)
            envelope_ = input_level;
        } else {
            // Release: exponential decay
            sample_value_t release_coeff = std::exp(sample_value_t(-1.0) /
                (release_ * sample_value_t(44100)));
            envelope_ = release_coeff * envelope_ +
                (sample_value_t(1.0) - release_coeff) * input_level;
        }

        // Compute gain reduction based on envelope level
        if (envelope_ > AudioConstants::DB_EPSILON) {
            sample_value_t env_db = linear_to_db(envelope_);

            if (env_db > threshold_db_) {
                // Signal exceeds threshold - apply compression
                sample_value_t over_db = env_db - threshold_db_;
                sample_value_t compressed_db = over_db / ratio_;
                sample_value_t reduction_db = over_db - compressed_db;
                sample_value_t gain = db_to_linear(-reduction_db);

                samples[i].left *= gain * makeup_gain_;
                samples[i].right *= gain * makeup_gain_;
            } else {
                // Below threshold - apply makeup gain only
                samples[i].left *= makeup_gain_;
                samples[i].right *= makeup_gain_;
            }
        }
    }
}

void CompressorProcessor::setParameter(const std::string& key, sample_value_t value)
{
    if (key == "ratio") {
        ratio_ = value;
    } else if (key == "threshold_db") {
        threshold_db_ = value;
    } else if (key == "attack") {
        attack_ = value;
    } else if (key == "release") {
        release_ = value;
    } else if (key == "makeup_gain") {
        makeup_gain_ = value;
    }
}

sample_value_t CompressorProcessor::getParameter(const std::string& key) const
{
    if (key == "ratio") return ratio_;
    if (key == "threshold_db") return threshold_db_;
    if (key == "attack") return attack_;
    if (key == "release") return release_;
    if (key == "makeup_gain") return makeup_gain_;
    if (key == "envelope") return envelope_;
    return sample_value_t(0);
}

void CompressorProcessor::reset()
{
    ratio_ = 4.0;
    threshold_db_ = -20.0;
    attack_ = 0.01;
    release_ = 0.1;
    envelope_ = 0.0;
    makeup_gain_ = 1.0;
}

} // namespace audiomix
