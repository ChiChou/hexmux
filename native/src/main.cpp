#include "hexmux/activation.hpp"

#include <exception>
#include <iostream>
#include <string>

namespace {

void usage(const char* program) {
    std::cerr << "usage: " << program
              << " [--socket-name NAME] -- PYTHON [-m hexmux.supervisor ...]\n";
}

}  // namespace

int main(int argc, char* argv[]) {
    std::string socket_name = "Listeners";
    int command_index = -1;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--" && index + 1 < argc) {
            command_index = index + 1;
            break;
        }
        if (argument == "--socket-name" && index + 1 < argc) {
            socket_name = argv[++index];
            continue;
        }
        usage(argv[0]);
        return 2;
    }
    if (command_index < 0) {
        usage(argv[0]);
        return 2;
    }

    try {
        auto endpoint = hexmux::acquire_activated_endpoint(socket_name);
        std::cerr << "hexmux-activate: inherited " << endpoint.source
                  << " listener as fd " << endpoint.fd << '\n';
        hexmux::exec_supervisor(endpoint.fd, argc, argv, command_index);
    } catch (const std::exception& error) {
        std::cerr << "hexmux-activate: " << error.what() << '\n';
        return 1;
    }
}
