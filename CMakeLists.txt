cmake_minimum_required (VERSION 3.1)
project (unicorn)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_C_STANDARD 23)
add_compile_options(-Wall -Wpedantic -Wextra -Werror)

include_directories(alpha4/src/)

add_subdirectory(c/)

if (${CMAKE_BUILD_TYPE} MATCHES "Debug")
add_compile_options(-Og -O0)
else()
  add_compile_options(-O3)
endif()