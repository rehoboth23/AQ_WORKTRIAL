#include "pipeline.h"
#include <algorithm>
#include <stdexcept>

namespace audiomix {

ProcessorChain::~ProcessorChain()
{
    // The chain does NOT own the processor pointers.
    // Cleanup is the responsibility of the caller.
    processors_.clear();
}

void ProcessorChain::addProcessor(AudioProcessor* proc)
{
    // Store the processor pointer. The chain does not take ownership.
    // Callers should ensure the processor remains valid for the
    // lifetime of the chain or until it is removed.
    processors_.push_back(proc);
}

void ProcessorChain::removeProcessor(AudioProcessor* proc)
{
    auto it = std::find(processors_.begin(), processors_.end(), proc);
    if (it != processors_.end()) {
        processors_.erase(it);
    }
}

void ProcessorChain::clear()
{
    processors_.clear();
}

void ProcessorChain::run(AudioSample* samples, size_t num_frames)
{
    if (!samples || num_frames == 0) {
        return;
    }

    // Execute each processor in order
    for (size_t i = 0; i < processors_.size(); ++i) {
        processors_[i]->process(samples, num_frames);
    }
}

AudioProcessor* ProcessorChain::getProcessor(size_t index) const
{
    if (index < processors_.size()) {
        return processors_[index];
    }
    return nullptr;
}

} // namespace audiomix
