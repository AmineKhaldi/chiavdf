CMAKE_MINIMUM_REQUIRED(VERSION 3.14 FATAL_ERROR)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "Release"
    CACHE STRING "Possible values are empty, Debug, Release, RelWithDebInfo, MinSizeRel, ..."
    FORCE
  )
endif()

project(chiavdf C CXX ASM)

set(CMAKE_MODULE_PATH
    ${CMAKE_CURRENT_LIST_DIR}/cmake
    ${CMAKE_MODULE_PATH}
)

if((CMAKE_BUILD_TYPE MATCHES "Release") AND NOT MSVC)
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -flto")
endif()

foreach(env_var IN ITEMS BUILD_VDF_BENCH ASAN TSAN)
  if((DEFINED ENV{${env_var}}) AND ($ENV{${env_var}} MATCHES "y|Y|1|t|T"))
    set(${env_var}_VALUE ON)
  else()
    set(${env_var}_VALUE OFF)
  endif()
endforeach()

if((DEFINED ENV{BUILD_VDF_CLIENT}) AND ($ENV{BUILD_VDF_CLIENT} MATCHES "n|N|0|f|F"))
  set(BUILD_VDF_CLIENT_VALUE OFF)
else()
  set(BUILD_VDF_CLIENT_VALUE ON)
endif()

option(BUILD_VDF_CLIENT "Whether to compile vdf client related targets" ${BUILD_VDF_CLIENT_VALUE})
message(STATUS "BUILD_VDF_CLIENT: ${BUILD_VDF_CLIENT}")
option(BUILD_VDF_BENCH "Whether to compile vdf bench related targets" ${BUILD_VDF_BENCH_VALUE})
message(STATUS "BUILD_VDF_BENCH: ${BUILD_VDF_BENCH}")
option(ASAN "Whether to compile targets with Address Sanitizer" ${ASAN_VALUE})
message(STATUS "ASAN: ${ASAN}")
option(TSAN "Whether to compile targets with Thread Sanitizer" ${TSAN_VALUE})
message(STATUS "TSAN: ${TSAN}")
if(ASAN AND TSAN)
  message(FATAL_ERROR "Please enable either ASAN or TSAN, they're not compatible with each other.")
endif()

# CMake 3.14+
include(FetchContent)

FetchContent_Declare(
  pybind11-src
  GIT_REPOSITORY https://github.com/pybind/pybind11.git
  GIT_TAG        v2.10.0
)
FetchContent_MakeAvailable(pybind11-src)

pybind11_add_module(chiavdf src/python_bindings/fastvdf.cpp)

add_library(lzcnt OBJECT src/refcode/lzcnt.c)

add_executable(verifier_test src/verifier_test.cpp)

if(MSVC)
  # We'll be using our custom MPIR build instead of GMP for MSVC builds
  FetchContent_Declare(
    chia_mpir
    GIT_REPOSITORY https://github.com/Chia-Network/mpir_gc_x64.git
    GIT_SHALLOW true
  )
  FetchContent_MakeAvailable(chia_mpir)
  file(GLOB chia_mpir_dlls ${chia_mpir_SOURCE_DIR}/*.dll)
else()
  find_package(GMP REQUIRED)
  find_package(GMPXX REQUIRED)
endif()

foreach(target IN ITEMS chiavdf verifier_test)
  target_link_libraries(${target} PRIVATE lzcnt)
  if(MSVC)
    target_include_directories(${target} PUBLIC ${chia_mpir_SOURCE_DIR})
    target_link_libraries(${target} PRIVATE ${chia_mpir_SOURCE_DIR}/mpir.lib)
    foreach(mpir_dll IN LISTS chia_mpir_dlls)
      add_custom_command(
        TARGET ${target}
        POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${mpir_dll} $<TARGET_FILE_DIR:${target}>
      )
    endforeach()
  else()
    target_include_directories(${target} PUBLIC ${GMP_INCLUDE_DIR} ${GMPXX_INCLUDE_DIR})
    target_link_libraries(${target} PRIVATE ${GMP_LIBRARIES} ${GMPXX_LIBRARIES})
  endif()
endforeach()

if(NOT MSVC)
  add_executable(compile_asm src/compile_asm.cpp)
  if(CMAKE_SYSTEM_NAME MATCHES "Darwin")
    target_compile_definitions(compile_asm PRIVATE CHIAOSX=1)
  endif()
  target_include_directories(compile_asm PUBLIC ${GMP_INCLUDE_DIR} ${GMPXX_INCLUDE_DIR})
  target_link_libraries(compile_asm PRIVATE lzcnt)
  target_link_libraries(compile_asm PRIVATE ${GMP_LIBRARIES} ${GMPXX_LIBRARIES})
  add_custom_command(
    OUTPUT
      ${CMAKE_CURRENT_BINARY_DIR}/asm_compiled.s
      ${CMAKE_CURRENT_BINARY_DIR}/avx2_asm_compiled.s
      ${CMAKE_CURRENT_BINARY_DIR}/avx512_asm_compiled.s
    COMMAND compile_asm
    COMMAND compile_asm avx2
    COMMAND compile_asm avx512
  )
  add_library(asm_files OBJECT
    ${CMAKE_CURRENT_BINARY_DIR}/asm_compiled.s
    ${CMAKE_CURRENT_BINARY_DIR}/avx2_asm_compiled.s
    ${CMAKE_CURRENT_BINARY_DIR}/avx512_asm_compiled.s
  )
  find_package(Boost REQUIRED COMPONENTS system)
  if(BUILD_VDF_CLIENT)
    add_executable(1weso_test src/1weso_test.cpp)
    add_executable(2weso_test src/2weso_test.cpp)
    add_executable(vdf_client src/vdf_client.cpp)
    add_executable(prover_test src/prover_test.cpp)
    add_executable(avx512_test src/avx512_test.cpp)
  endif()
  if(BUILD_VDF_BENCH)
    add_executable(vdf_bench src/vdf_bench.cpp)
  endif()
  foreach(target IN ITEMS 1weso_test 2weso_test avx512_test prover_test vdf_bench vdf_client)
    if(TARGET ${target})
      if(CMAKE_SYSTEM_NAME MATCHES "Darwin")
        target_compile_definitions(${target} PRIVATE CHIAOSX=1)
      endif()
      target_compile_definitions(${target} PRIVATE VDF_MODE=0)
      if(ASAN)
        target_compile_options(${target} PRIVATE -fsanitize=address -fsanitize=undefined -fsanitize-undefined-trap-on-error)
        target_link_options(${target} PRIVATE -fsanitize=address -fsanitize=undefined)
      endif()
      if(TSAN)
        target_compile_options(${target} PRIVATE -g -fsanitize=thread)
        target_link_options(${target} PRIVATE -fsanitize=thread)
      endif()
      target_link_options(${target} PRIVATE -no-pie)
      target_include_directories(${target} PUBLIC ${GMP_INCLUDE_DIR} ${GMPXX_INCLUDE_DIR})
      target_link_libraries(${target} PRIVATE asm_files ${GMP_LIBRARIES} ${GMPXX_LIBRARIES} lzcnt)
    endif()
  endforeach()
endif()
