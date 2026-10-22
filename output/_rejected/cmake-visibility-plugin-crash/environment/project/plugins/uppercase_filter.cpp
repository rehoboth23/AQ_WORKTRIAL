#include <csvtools/filter.h>
#include <algorithm>
#include <cctype>

namespace csvtools {

class UppercaseFilter : public Filter {
public:
    std::string apply(const std::string& value) const override {
        std::string result = value;
        std::transform(result.begin(), result.end(), result.begin(),
                       [](unsigned char c) { return std::toupper(c); });
        return result;
    }
};

namespace {
struct UppercaseFilterInit {
    UppercaseFilterInit() {
        static UppercaseFilter instance;
        register_filter("uppercase", &instance);
    }
};
static UppercaseFilterInit init;
} // namespace

} // namespace csvtools
