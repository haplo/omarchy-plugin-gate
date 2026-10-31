# The bash and fish completion scripts, run against this build.

demo_clone
mkdir -p "$B/state/demo" "$B/other-root/second"
printf '0123456789abcdef0123456789abcdef01234567\nwhy\n' >"$B/state/demo/held"
printf '{"id": "second"}\n' >"$B/other-root/second/manifest.json"

printf '\n== bash completion ==\n'
# The words after the command, as readline hands them over: --opt=value arrives
# as --opt, = and value. The last word is the one being completed.
bash_complete() {
  bash -c '
    source "$1"
    shift
    COMP_WORDS=("$@")
    COMP_CWORD=$(($# - 1))
    _omarchy_plugin_gate
    printf "%s\n" "${COMPREPLY[@]}"
  ' _ "$REPO/completions/omarchy-plugin-gate.bash" "$GATE" "$@" 2>&1
}
eq 'bash completion offers plugin names' "$(bash_complete status -p de)" demo
eq 'bash completion offers the held commit for --sha' \
  "$(bash_complete approve demo --sha '')" 0123456789ab
eq 'bash completion reads --plugin=NAME' \
  "$(bash_complete approve --plugin = demo --sha '')" 0123456789ab
eq 'bash completion completes after --plugin=' "$(bash_complete status --plugin = de)" demo
eq 'bash completion completes after --notify=' "$(bash_complete status --notify = r)" ready
eq 'bash completion uses --root from the line' \
  "$(bash_complete --root "$B/other-root" status -p '')" second
eq 'bash completion uses --root= from the line' \
  "$(bash_complete status --root = "$B/other-root" -p '')" second
eq 'bash completion expands ~ in --root' \
  "$(HOME=$B bash_complete --root '~/other-root' status -p '')" second
eq 'bash completion offers no second plugin to approve' "$(bash_complete approve demo '')" ''
eq 'bash completion offers --version before the command' "$(bash_complete --ver)" --version
eq 'bash completion offers no --version after the command' "$(bash_complete status --ver)" ''

printf '\n== fish completion ==\n'
if command -v fish >/dev/null 2>&1; then
  # fish runs `omarchy-plugin-gate` from PATH, so put this build there.
  mkdir -p "$B/fish-bin"
  ln -sfn "$GATE" "$B/fish-bin/omarchy-plugin-gate"
  fish_complete() {
    PATH="$B/fish-bin:$PATH" fish --no-config -c '
      source $argv[1]
      complete -C"omarchy-plugin-gate $argv[2]" | string replace -r "\t.*" ""
    ' "$REPO/completions/omarchy-plugin-gate.fish" "$1" 2>&1
  }
  eq 'fish completion offers plugin names to approve' "$(fish_complete 'approve de')" demo
  eq 'fish completion offers no second plugin to approve' "$(fish_complete 'approve demo ')" ''
  eq 'fish completion offers no positional after --plugin' \
    "$(fish_complete 'approve --plugin demo ')" ''
  eq 'fish completion offers the held commit for --sha' \
    "$(fish_complete 'approve demo --sha ')" 0123456789ab
  eq 'fish completion uses --root from the line' \
    "$(fish_complete "--root $B/other-root status -p ")" second
  eq 'fish completion offers no --version after the command' "$(fish_complete 'status --ver')" ''
else
  ok 'fish completion (skipped: fish not installed)'
fi
