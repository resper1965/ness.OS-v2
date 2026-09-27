#!/usr/bin/env bash

psono_account_value() {
  local report="$1" key="$2"
  awk -F= -v key="${key}" '$1 == key { print $2; found = 1 } END { if (!found) exit 1 }' \
    <<<"${report}"
}

psono_positive_count() {
  [[ $1 =~ ^[0-9]+$ ]] && (( $1 > 0 ))
}

psono_mfa_readiness() {
  local report="$1" mfa_enforced="$2" recovery_tested="$3"
  local custodian active superuser password_change_required mfa recovery_count emergency_count
  for custodian in resper iaraujo; do
    active="$(psono_account_value "${report}" "custodian_${custodian}_active")" || return 1
    superuser="$(psono_account_value "${report}" "custodian_${custodian}_superuser")" || return 1
    password_change_required="$(psono_account_value "${report}" "custodian_${custodian}_password_change_required")" || return 1
    mfa="$(psono_account_value "${report}" "custodian_${custodian}_mfa")" || return 1
    recovery_count="$(psono_account_value "${report}" "custodian_${custodian}_recovery_codes")" || return 1
    [[ ${active} == yes && ${superuser} == yes && ${password_change_required} == no && ${mfa} == yes ]] || return 1
    psono_positive_count "${recovery_count}" || return 1
  done
  emergency_count="$(psono_account_value "${report}" emergency_code_count)" || return 1
  psono_positive_count "${emergency_count}" || return 1
  [[ ${mfa_enforced} == yes && ${recovery_tested} == yes ]]
}
