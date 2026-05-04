cmake_minimum_required(VERSION 3.10)

project(radiology)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Include directories
include_directories(${CMAKE_SOURCE_DIR}/include)

# Collect all source files
file(GLOB_RECURSE SOURCES 
    "${CMAKE_SOURCE_DIR}/src/*.cpp"
)

# Collect all header files
file(GLOB_RECURSE HEADERS 
    "${CMAKE_SOURCE_DIR}/include/*.hpp"
)

# Create executable
add_executable(radiology 
    main.cpp
    ${SOURCES}
    ${HEADERS}
)


