#include <csvtools/capi.h>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        return 1;
    }
    csvtools_add_plugin_path("plugins");
    csvtools_process(argv[1]);
    return 0;
}
