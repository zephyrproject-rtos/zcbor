#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#

cmake_minimum_required(VERSION 3.13.1)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(test3_unit_tests)

include(../../cmake/test_template.cmake)

FILE(GLOB zcbor_sources ../../../src/*.c)
target_sources(app PRIVATE
  ${zcbor_sources})

target_include_directories(app PRIVATE ../../../include)

if (VERBOSE)
  return() # Because the output volume is too large
endif()

if (CONFIG_NATIVE_BUILD AND NOT CONFIG_64BIT)
  set (LD_SIMULATION -m elf_i386)
endif()

set(LD ld)
if(NOT CONFIG_NATIVE_BUILD)
  set(LD ${CROSS_COMPILE_TARGET}-ld)
  if(DEFINED ENV{ZEPHYR_SDK_INSTALL_DIR})
    set(LD $ENV{ZEPHYR_SDK_INSTALL_DIR}/${CROSS_COMPILE_TARGET}/bin/${LD})
  endif()
endif()

if(DEFINED CMAKE_LINKER)
  set(LD ${CMAKE_LINKER})
endif()

execute_process(COMMAND ${CMAKE_COMMAND} -E make_directory ${PROJECT_BINARY_DIR}/include)

function(zcbor_add_binary_obj OUT_VAR BIN_NAME)
  set(bin_src ${CMAKE_CURRENT_LIST_DIR}/${BIN_NAME}.bin)
  set(bin_dst ${PROJECT_BINARY_DIR}/${BIN_NAME}.bin)
  set(obj_out ${PROJECT_BINARY_DIR}/${BIN_NAME}.o)

  add_custom_command(
    OUTPUT ${obj_out}
    COMMAND ${CMAKE_COMMAND} -E copy ${bin_src} ${bin_dst}
    COMMAND ${LD} ${LD_SIMULATION} -r -b binary -o ${obj_out} ${BIN_NAME}.bin
    WORKING_DIRECTORY ${PROJECT_BINARY_DIR}
    DEPENDS ${bin_src}
    VERBATIM
  )

  set(${OUT_VAR} ${obj_out} PARENT_SCOPE)
endfunction()

zcbor_add_binary_obj(FP_DECODE_OBJ fp_bytes_decode)
zcbor_add_binary_obj(FP_ENCODE_OBJ fp_bytes_encode)

add_custom_target(fp_bytes_objs DEPENDS ${FP_DECODE_OBJ} ${FP_ENCODE_OBJ})
add_dependencies(app fp_bytes_objs)
target_link_libraries(app PRIVATE ${FP_DECODE_OBJ} ${FP_ENCODE_OBJ})
