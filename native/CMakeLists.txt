cmake_minimum_required(VERSION 3.20)
project(hexmux_activate LANGUAGES CXX)

add_executable(hexmux-activate
    src/main.cpp
)
target_compile_features(hexmux-activate PRIVATE cxx_std_20)
target_include_directories(hexmux-activate PRIVATE include)

if(APPLE)
    target_sources(hexmux-activate PRIVATE src/activation_launchd.cpp src/process_posix.cpp)
elseif(UNIX)
    target_sources(hexmux-activate PRIVATE src/activation_systemd.cpp src/process_posix.cpp)
else()
    message(FATAL_ERROR "The native activator currently supports launchd and systemd")
endif()

install(TARGETS hexmux-activate RUNTIME DESTINATION bin)
