#include "hexmux/activation.hpp"

#include <cstdlib>
#include <stdexcept>
#include <string>
#include <unistd.h>

namespace hexmux {

ActivatedEndpoint acquire_activated_endpoint(const std::string&) {
    const char* pid_text = std::getenv("LISTEN_PID");
    const char* count_text = std::getenv("LISTEN_FDS");
    if (pid_text == nullptr || count_text == nullptr) {
        throw std::runtime_error("LISTEN_PID/LISTEN_FDS are not set");
    }
    if (std::stol(pid_text) != static_cast<long>(getpid())) {
        throw std::runtime_error("LISTEN_PID does not match this process");
    }
    if (std::stol(count_text) != 1) {
        throw std::runtime_error("expected exactly one systemd socket");
    }
    unsetenv("LISTEN_PID");
    unsetenv("LISTEN_FDS");
    unsetenv("LISTEN_FDNAMES");
    return {.fd = 3, .source = "systemd"};
}

}  // namespace hexmux
