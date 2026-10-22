#include "cli.h"

#include <iostream>
#include <cstdlib>

int main(int argc, char* argv[])
{
    try {
        audiomix::CliApp app;
        int result = app.run(argc, argv);
        return result;
    } catch (const std::exception& e) {
        std::cerr << "Fatal error: " << e.what() << std::endl;
        return 2;
    } catch (...) {
        std::cerr << "Unknown fatal error" << std::endl;
        return 2;
    }
}
