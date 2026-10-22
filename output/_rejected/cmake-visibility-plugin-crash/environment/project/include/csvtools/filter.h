#ifndef CSVTOOLS_FILTER_H
#define CSVTOOLS_FILTER_H

#include <csvtools/export.h>
#include <string>

namespace csvtools {

class CSVTOOLS_API Filter {
public:
    virtual ~Filter();
    virtual std::string apply(const std::string& value) const = 0;
};

void register_filter(const std::string& name, Filter* filter);

} // namespace csvtools

#endif
