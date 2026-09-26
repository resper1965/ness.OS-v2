#!/usr/bin/env bash
set -euo pipefail

script="$(dirname "$0")/../scripts/hub-cavan-vm-cutover.sh"
status=0
output="$(bash "$script" 2>&1)" || status=$?

[[ "$status" -eq 2 ]]
[[ "$output" == *"Refusing cutover without --apply"* ]]
echo 'Cavan VM cutover requires explicit apply: PASS'
