#include "hexmux/activation.hpp"

#include <cerrno>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <launch.h>

namespace hexmux {

ActivatedEndpoint acquire_activated_endpoint(const std::string& name) {
    int* descriptors = nullptr;
    std::size_t count = 0;
    const int error = launch_activate_socket(name.c_str(), &descriptors, &count);
    if (error != 0) {
        throw std::runtime_error("launch_activate_socket(" + name + "): " + std::to_string(error));
    }
    if (count != 1) {
        std::free(descriptors);
        throw std::runtime_error("expected exactly one launchd socket, received " + std::to_string(count));
    }
    const int fd = descriptors[0];
    std::free(descriptors);
    return {.fd = fd, .source = "launchd"};
}

}  // namespace hexmux
