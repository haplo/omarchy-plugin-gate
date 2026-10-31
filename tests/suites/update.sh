# update moves the installed copy, but only to a reviewed or waived commit.

demo_approved
install_copy

printf '\n== update ==\n'
commit_upstream 'printf "// second\n" >> Widget.qml' second
"$GATE" check >/dev/null 2>&1
before=$(git -C "$idir" rev-parse HEAD)
"$GATE" update >/dev/null 2>&1
eq 'installed copy moved to approved' "$(git -C "$idir" rev-parse HEAD)" "$(ap)"
refute 'it actually moved' test "$before" = "$(ap)"

printf '\n== update refuses an unreviewed commit ==\n'
commit_upstream 'printf "// third\n" >> Widget.qml' third
"$GATE" check >/dev/null 2>&1
rm -f "$B/state/demo/reviewed/$(ap)"
snapshot=$(git -C "$idir" rev-parse HEAD)
out=$("$GATE" update 2>&1)
eq 'installed copy untouched' "$(git -C "$idir" rev-parse HEAD)" "$snapshot"
has <(printf '%s' "$out") 'no review or waiver record' 'refusal explained'
