#include <csvtools/capi.h>
#include <string>

namespace csvtools {
void process_csv(const std::string& filename);
void add_plugin_dir(const std::string& dir);
}

extern "C" {

void csvtools_process(const char* filename) {
    csvtools::process_csv(filename);
}

void csvtools_add_plugin_path(const char* path) {
    csvtools::add_plugin_dir(path);
}

}
