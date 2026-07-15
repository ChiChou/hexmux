#include "hexmux/activation.hpp"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <stdexcept>
#include <string>
#include <unistd.h>
#include <vector>

namespace hexmux {

[[noreturn]] void exec_supervisor(int fd, int argc, char* argv[], int command_index) {
    constexpr int target_fd = 3;
    if (fd != target_fd && dup2(fd, target_fd) < 0) {
        throw std::runtime_error("dup2: " + std::string(std::strerror(errno)));
    }
    if (fd != target_fd) {
        close(fd);
    }
    const int descriptor_flags = fcntl(target_fd, F_GETFD);
    if (descriptor_flags < 0 || fcntl(target_fd, F_SETFD, descriptor_flags & ~FD_CLOEXEC) < 0) {
        throw std::runtime_error("fcntl: " + std::string(std::strerror(errno)));
    }

    std::vector<char*> command;
    command.reserve(static_cast<std::size_t>(argc - command_index) + 4);
    for (int index = command_index; index < argc; ++index) {
        command.push_back(argv[index]);
    }
    command.push_back(const_cast<char*>("--listen-fd"));
    command.push_back(const_cast<char*>("3"));
    command.push_back(nullptr);

    execvp(command[0], command.data());
    throw std::runtime_error("execvp " + std::string(command[0]) + ": " + std::strerror(errno));
}

}  // namespace hexmux
