#pragma once

#include <string>

namespace hexmux {

struct ActivatedEndpoint {
    int fd = -1;
    std::string source;
};

ActivatedEndpoint acquire_activated_endpoint(const std::string& name);
[[noreturn]] void exec_supervisor(int fd, int argc, char* argv[], int command_index);

}  // namespace hexmux
