# Assertions. Each prints one line; a failure is also appended to $FAILED,
# prefixed with the running $SUITE, so the runner can count and list them.

ok() { printf '  ok    %s\n' "$1"; }
no() {
  printf '  FAIL  %s\n' "$1"
  printf '%s: %s\n' "$SUITE" "$1" >>"$FAILED"
}
eq() { if [[ "$2" == "$3" ]]; then ok "$1"; else no "$1 (got '$2', want '$3')"; fi; }
has() { if grep -qF -- "$2" "$1" 2>/dev/null; then ok "$3"; else no "$3"; fi; }

assert() { # assert <label> <command...>: passes when the command succeeds
  local label=$1
  shift
  if "$@"; then ok "$label"; else no "$label"; fi
}

refute() { # refute <label> <command...>: passes when the command fails
  local label=$1
  shift
  if "$@"; then no "$label"; else ok "$label"; fi
}
