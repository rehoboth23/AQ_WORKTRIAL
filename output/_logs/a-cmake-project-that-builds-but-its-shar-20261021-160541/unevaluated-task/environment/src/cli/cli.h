#pragma once

/// @file cli.h
/// @brief Command-line interface for the audiomix tool.
///
/// Provides the CLI application that handles command parsing and
/// dispatches to the appropriate processing or analysis function.

#include <string>
#include <vector>

namespace audiomix {

/// Command-line application for audiomix.
///
/// Parses command-line arguments and dispatches to either the
/// process or analyze subcommand.
class CliApp {
public:
    CliApp() = default;
    ~CliApp() = default;

    /// Run the CLI application.
    /// @param argc Argument count
    /// @param argv Argument values
    /// @return Exit code (0 = success, 1 = error, 2 = usage)
    int run(int argc, char* argv[]);

private:
    /// Handle the 'process' subcommand.
    int cmd_process(const std::vector<std::string>& args);

    /// Handle the 'analyze' subcommand.
    int cmd_analyze(const std::vector<std::string>& args);

    /// Print usage information.
    void print_usage(const std::string& prog_name);

    /// Print version information.
    void print_version();
};

} // namespace audiomix
