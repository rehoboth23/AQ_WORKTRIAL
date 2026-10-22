#include <csvtools/filter.h>

namespace csvtools {

class TrimFilter : public Filter {
public:
    std::string apply(const std::string& value) const override {
        size_t start = value.find_first_not_of(" \t\r\n");
        if (start == std::string::npos) return "";
        size_t end = value.find_last_not_of(" \t\r\n");
        return value.substr(start, end - start + 1);
    }
};

namespace {
struct TrimFilterInit {
    TrimFilterInit() {
        static TrimFilter instance;
        register_filter("trim", &instance);
    }
};
static TrimFilterInit init;
} // namespace

} // namespace csvtools
