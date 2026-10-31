# The post-merge tripwire: rolls back rejected upstream commits, never local work.

demo_approved

printf '\n== hooks leave local work alone ==\n'
"$GATE" doctor --fix >/dev/null 2>&1
( cd "$B/root/demo" && git checkout -q -b feature && printf '// local work\n' > Local.qml &&
  git add -A && git -c commit.gpgsign=false commit -qm 'local feature' &&
  git checkout -q main && git merge -q --ff-only feature )
local_sha=$(git -C "$B/root/demo" rev-parse HEAD)
refute 'own commit not reviewed' test -f "$B/state/demo/reviewed/$local_sha"
eq 'own commit kept' "$(git -C "$B/root/demo" rev-parse HEAD)" "$local_sha"
git -C "$B/root/demo" reset -q --hard origin/main

printf '\n== tripwire ==\n'
install_copy
"$GATE" doctor --fix >/dev/null 2>&1
assert 'hook in the clone' test -x "$B/root/demo/.git/hooks/post-merge"
assert 'hook in the installed copy' test -x "$idir/.git/hooks/post-merge"
has "$B/root/demo/.git/hooks/post-merge" "--root $B/root --state $B/state _post-merge" 'hook records root and state'
base=$(git -C "$B/root/demo" rev-parse HEAD)
commit_upstream 'printf "// NEEDS-HUMAN\n" >> Widget.qml' 'bad pull'
STUB_FAIL_ON=NEEDS-HUMAN bash -c "cd '$B/root/demo' && git pull -q --ff-only origin main" >/dev/null 2>&1
eq 'rejected pull rolled back' "$(git -C "$B/root/demo" rev-parse HEAD)" "$base"
commit_upstream 'printf "// fine\n" >> Widget.qml' 'good pull'
good=$(git -C "$B/upstream" rev-parse HEAD)
OMARCHY_PLUGIN_GATE_ROOT=$B/nowhere OMARCHY_PLUGIN_GATE_STATE=$B/wrong-state \
  bash -c "cd '$B/root/demo' && git pull -q --ff-only origin main" >/dev/null 2>&1
eq 'clean pull kept' "$(git -C "$B/root/demo" rev-parse HEAD)" "$good"
assert 'hook wrote a marker in its recorded state' test -f "$B/state/demo/reviewed/$good"
refute 'hook ignores the environment paths' test -e "$B/wrong-state"
has "$idir/.git/hooks/post-merge" '_post-merge demo "$top"' 'hook names its plugin'

base=$(ap)
reset_upstream "$base"
commit_upstream 'jq ".id = \"selftest.other\"" manifest.json > m && mv m manifest.json' 'change the id'
git -C "$B/root/demo" fetch -q origin
renamed=$(upstream_sha)
before=$(git -C "$idir" rev-parse HEAD)
: >"$OMARCHY_LOG"
n0=$(invocations)
bash -c "cd '$idir' && git pull -q --ff-only origin refs/remotes/origin/main" >/dev/null 2>&1
eq 'id change: installed copy rolled back' "$(git -C "$idir" rev-parse HEAD)" "$before"
has "$B/state/demo/reviews/${renamed:0:12}/verdict" 'manifest id changed' 'id change: reviewed by the hook'
eq 'id change: reviewer skipped' "$(invocations)" "$n0"
has "$OMARCHY_LOG" 'plugin disable selftest.demo' 'id change: approved id disabled'
