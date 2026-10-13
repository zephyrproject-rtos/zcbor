#!/bin/bash
#
# Copyright (c) 2020 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0
#

set -eu

pushd "tests/scripts"
python3 -m unittest test_zcbor test_repo_files
[[ $? -ne 0 ]] && popd && exit 1
popd

if ! command -v west >/dev/null 2>&1; then
        echo "west not found; cannot run Zephyr twister tests." >&2
        exit 1
fi

west twister -M -v -T . -W --exclude-tag release \
        --platform native_sim \
        --platform native_sim/native/64 \
        --platform mps2/an521/cpu0 \
        "$@"
