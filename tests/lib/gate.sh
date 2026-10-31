# Helpers for driving the gate against the demo plugin.

ap() { git -C "$B/root/demo" rev-parse --verify -q refs/heads/gate-approved || true; }
upstream_sha() { git -C "$B/root/demo" rev-parse origin/main; }
invocations() { grep -c '^stub-invoked' "$STUB_LOG" 2>/dev/null || printf 0; }
vdir() { ls -1dt "$B"/state/demo/reviews/*/ 2>/dev/null | head -1; }
last_verdict() { head -1 "$(vdir)verdict" 2>/dev/null || true; }

reset_upstream() { # move upstream back to an approved commit
  git -C "$B/upstream" reset -q --hard "$1"
  git -C "$B/upstream" push -q -f "$B/upstream.git" main
  git -C "$B/root/demo" fetch -q origin
}

commit_upstream() { # commit_upstream <shell expression> <message>
  ( cd "$B/upstream" && eval "$1" && git add -A && git -c commit.gpgsign=false commit -qm "$2" &&
    git push -q "$B/upstream.git" main )
}

case_hard() { # case_hard <label> <expression> <expected reason substring> [VAR=value ...]
  local label=$1 expr=$2 want=$3 base n0 n1
  shift 3
  base=$(ap)
  reset_upstream "$base"
  commit_upstream "$expr" "$label"
  n0=$(invocations)
  env "$@" "$GATE" check >/dev/null 2>&1
  n1=$(invocations)
  eq "$label: reviewer skipped" "$n1" "$n0"
  eq "$label: approved unchanged" "$(ap)" "$base"
  eq "$label: verdict FAIL" "$(last_verdict)" "REVIEW FAIL"
  has "$(vdir)verdict" "$want" "$label: reason"
}

case_finding() { # case_finding <label> <expression> <expected finding substring>
  local label=$1 expr=$2 want=$3 base n0 n1 out
  base=$(ap)
  reset_upstream "$base"
  commit_upstream "$expr" "$label"
  n0=$(invocations)
  out=$("$GATE" check 2>&1)
  n1=$(invocations)
  eq "$label: reviewer consulted" "$((n1 - n0))" 1
  has "$(vdir)findings.txt" "$want" "$label: finding recorded"
  has <(printf '%s\n' "$out" | grep -E '^    F1 ') "$want" "$label: finding printed"
  has "$STUB_PROMPT" "$want" "$label: finding in the prompt"
  eq "$label: verdict PASS once cleared" "$(last_verdict)" "REVIEW PASS"
  eq "$label: approved advanced" "$(ap)" "$(upstream_sha)"
  has "$(vdir)cleared" 'cleared: ' "$label: clearance recorded"
}

case_uncleared() { # case_uncleared <label> <expression> <expected reason substring> [VAR=value ...]
  local label=$1 expr=$2 want=$3 base n0 n1
  shift 3
  base=$(ap)
  reset_upstream "$base"
  commit_upstream "$expr" "$label"
  n0=$(invocations)
  env "$@" "$GATE" check >/dev/null 2>&1
  n1=$(invocations)
  eq "$label: reviewer consulted" "$((n1 - n0))" 1
  eq "$label: approved unchanged" "$(ap)" "$base"
  eq "$label: verdict FAIL" "$(last_verdict)" "REVIEW FAIL"
  has "$(vdir)verdict" "$want" "$label: reason"
  refute "$label: no clearance recorded" test -f "$(vdir)cleared"
  reset_upstream "$base"
}
