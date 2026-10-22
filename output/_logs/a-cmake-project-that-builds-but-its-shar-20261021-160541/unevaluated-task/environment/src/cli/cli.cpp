#include "cli.h"
#include "audiomix/audiomix.h"
#include "audiomix/api.h"

#include <iostream>
#include <string>
#include <vector>
#include <dlfcn.h>
#include <cstdlib>
#include <cstring>

namespace audiomix {

void CliApp::print_usage(const std::string& prog_name)
{
    std::cerr << "Usage: " << prog_name << " <command> [args...]\n\n"
              << "Commands:\n"
              << "  process <input.wav> <output.wav> <processor> <param>\n"
              << "    Apply an audio processor to a WAV file.\n"
              << "    Processors: normalize, gain, limiter, compressor\n\n"
              << "  analyze <input.wav>\n"
              << "    Analyze a WAV file and print metrics.\n\n"
              << "  version\n"
              << "    Print version information.\n";
}

void CliApp::print_version()
{
    std::cout << "audiomix-cli version " << audiomix::version() << "\n"
              << "Precision mode: " << audiomix::precision_mode() << "\n"
              << "AudioSample size: " << audiomix::audio_sample_size() << " bytes\n";
}

int CliApp::cmd_process(const std::vector<std::string>& args)
{
    if (args.size() < 4) {
        std::cerr << "Error: process command requires 4 arguments\n"
                  << "Usage: audiomix-cli process <input.wav> <output.wav> "
                  << "<processor> <param>\n";
        return 1;
    }

    const std::string& input_file = args[0];
    const std::string& output_file = args[1];
    const std::string& processor_type = args[2];
    const std::string& param_str = args[3];

    // Parse parameter as double
    double param = 0.0;
    try {
        param = std::stod(param_str);
    } catch (const std::exception&) {
        std::cerr << "Error: invalid parameter value: " << param_str << "\n";
        return 1;
    }

    // Validate processor type
    if (processor_type != "normalize" && processor_type != "gain" &&
        processor_type != "limiter" && processor_type != "compressor") {
        std::cerr << "Error: unknown processor type: " << processor_type << "\n"
                  << "Valid types: normalize, gain, limiter, compressor\n";
        return 1;
    }

    // Run the processing pipeline
    audioformat::PipelineRunner runner;
    int result = runner.run(input_file, output_file, processor_type, param);

    if (result != 0) {
        std::cerr << "Error: processing failed: " << runner.last_error() << "\n";
    }

    return result;
}

int CliApp::cmd_analyze(const std::vector<std::string>& args)
{
    if (args.size() < 1) {
        std::cerr << "Error: analyze command requires 1 argument\n"
                  << "Usage: audiomix-cli analyze <input.wav>\n";
        return 1;
    }

    const std::string& input_file = args[0];

    // The analysis module is loaded dynamically for plugin compatibility.
    // This allows the analysis functionality to be provided by an
    // optional plugin that may not always be installed.
    void* handle = dlopen(nullptr, RTLD_LAZY);
    if (!handle) {
        std::cerr << "Error: analysis module not available" << std::endl;
        return 1;
    }

    // Look up the analyze function
    using AnalyzeFunc = int (*)(const char*, char*, size_t);
    AnalyzeFunc analyze = reinterpret_cast<AnalyzeFunc>(dlsym(handle, "audiomix_analyze_file"));

    if (!analyze) {
        std::cerr << "Error: analysis module not available" << std::endl;
        dlclose(handle);
        return 1;
    }

    // Call the analyze function
    char result_buf[1024];
    memset(result_buf, 0, sizeof(result_buf));

    int rc = analyze(input_file.c_str(), result_buf, sizeof(result_buf));

    if (rc == 0) {
        std::cout << result_buf << std::endl;
    } else {
        std::cerr << "Error: analysis failed for file: " << input_file << std::endl;
    }

    dlclose(handle);
    return rc;
}

int CliApp::run(int argc, char* argv[])
{
    if (argc < 2) {
        print_usage(argv[0]);
        return 2;
    }

    std::string command = argv[1];

    // Collect remaining arguments
    std::vector<std::string> args;
    for (int i = 2; i < argc; ++i) {
        args.emplace_back(argv[i]);
    }

    if (command == "process") {
        return cmd_process(args);
    } else if (command == "analyze") {
        return cmd_analyze(args);
    } else if (command == "version" || command == "--version" || command == "-v") {
        print_version();
        return 0;
    } else if (command == "help" || command == "--help" || command == "-h") {
        print_usage(argv[0]);
        return 0;
    } else {
        std::cerr << "Error: unknown command: " << command << "\n";
        print_usage(argv[0]);
        return 2;
    }
}

} // namespace audiomix
