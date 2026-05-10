When compiling the main.cpp file, make sure you are also compiling everything in the src/ folder AND are also including all the header-files present in include/

For VSCode-users, a tasks.json configuration file can be found in .vscode. This file uses clang++ as the compiler. Make sure to adjust the paths to your own setup if necessary.

For CMake-users, a CMakeLists.txt file is provided. You can generate your build files using CMake and then use these in your preferred IDE / terminal.
