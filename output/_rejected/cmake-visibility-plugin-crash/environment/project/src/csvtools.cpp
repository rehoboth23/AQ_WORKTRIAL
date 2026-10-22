#include <csvtools/filter.h>
#include <csvtools/detail/validate.h>

#include <algorithm>
#include <dlfcn.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <vector>

namespace csvtools {

Filter::~Filter() = default;

static std::map<std::string, Filter*>& get_registry() {
    static std::map<std::string, Filter*> registry;
    return registry;
}

void register_filter(const std::string& name, Filter* filter) {
    get_registry()[name] = filter;
}

namespace detail {

bool validate_plugin_path(const std::string& path) {
    return std::filesystem::exists(path);
}

} // namespace detail

static std::vector<std::string> plugin_dirs;

void add_plugin_dir(const std::string& dir) {
    plugin_dirs.push_back(dir);
}

static void load_plugins() {
    for (const auto& dir : plugin_dirs) {
        if (!std::filesystem::exists(dir)) continue;
        std::vector<std::string> files;
        for (const auto& entry : std::filesystem::directory_iterator(dir)) {
            if (entry.is_regular_file() && entry.path().extension() == ".so") {
                files.push_back(entry.path().string());
            }
        }
        std::sort(files.begin(), files.end());
        for (const auto& path : files) {
            if (!detail::validate_plugin_path(path)) continue;
            void* handle = dlopen(path.c_str(), RTLD_NOW);
            if (!handle) {
                std::cerr << "Failed to load plugin: " << path << " - " << dlerror() << std::endl;
                continue;
            }
        }
    }
}

void process_csv(const std::string& filename) {
    load_plugins();

    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Cannot open file: " << filename << std::endl;
        return;
    }

    std::string line;
    while (std::getline(file, line)) {
        std::vector<std::string> fields;
        std::stringstream ss(line);
        std::string field;
        while (std::getline(ss, field, ',')) {
            fields.push_back(field);
        }

        for (auto& f : fields) {
            for (auto& [name, filter] : get_registry()) {
                f = filter->apply(f);
            }
        }

        for (size_t i = 0; i < fields.size(); i++) {
            if (i > 0) std::cout << ",";
            std::cout << fields[i];
        }
        std::cout << "\n";
    }
}

} // namespace csvtools
