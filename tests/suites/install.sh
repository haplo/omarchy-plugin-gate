# scripts/install.sh and scripts/uninstall.sh against a scratch home.

ih=$B/install-home
iconf=$ih/cfg/omarchy-plugin-gate/config.toml
mkdir -p "$ih"
inst() {
  env -u OMARCHY_PLUGIN_GATE_ROOT -u OMARCHY_PLUGIN_GATE_STATE -u XDG_STATE_HOME \
    HOME="$ih" XDG_CONFIG_HOME="$ih/cfg" XDG_DATA_HOME="$ih/data" \
    OMARCHY_PLUGIN_GATE_BIN_DIR="$ih/bin" "$@"
}

printf '\n== install ==\n'
out=$(inst "$REPO/scripts/install.sh" --no-timer 2>&1)
eq 'install exits 0' "$?" 0
assert 'example config copied' cmp -s "$iconf" "$REPO/config.example.toml"
has <(printf '%s' "$out") "config    $iconf (created" 'install reports the new config'
assert 'default state created' test -d "$ih/.local/state/omarchy-plugin-gate"
printf 'state = "~/gate-state"\n' >>"$iconf"
cp "$iconf" "$B/config.before"
out=$(inst "$REPO/scripts/install.sh" --no-timer 2>&1)
eq 'reinstall exits 0' "$?" 0
assert 'reinstall keeps the config' cmp -s "$iconf" "$B/config.before"
has <(printf '%s' "$out") "config    $iconf (kept)" 'install reports the kept config'
assert 'install uses the state from the config file' test -d "$ih/gate-state"

bashc=$ih/data/bash-completion/completions/omarchy-plugin-gate
fishc=$ih/data/fish/vendor_completions.d/omarchy-plugin-gate.fish
zshc=$ih/data/zsh/site-functions/_omarchy-plugin-gate
assert 'bash completion linked' test -L "$bashc"
assert 'fish completion linked' test -L "$fishc"
assert 'zsh completion linked' test -L "$zshc"
assert 'bash completion points at the repository' cmp -s "$bashc" "$REPO/completions/omarchy-plugin-gate.bash"
has <(printf '%s' "$out") "bash  $bashc" 'install reports the completions'

printf '\n== uninstall ==\n'
out=$(inst "$REPO/scripts/uninstall.sh" 2>&1)
eq 'uninstall exits 0' "$?" 0
refute 'uninstall removes the command' test -e "$ih/bin/omarchy-plugin-gate"
assert 'uninstall keeps the config' cmp -s "$iconf" "$B/config.before"
has <(printf '%s' "$out") "review evidence  $ih/gate-state" 'uninstall uses the state from the config file'
refute 'uninstall removes the bash completion' test -L "$bashc"
refute 'uninstall removes the fish completion' test -L "$fishc"
refute 'uninstall removes the zsh completion' test -L "$zshc"
printf '#!/usr/bin/env bash\n' >"$bashc"
inst "$REPO/scripts/uninstall.sh" >/dev/null 2>&1
assert 'uninstall keeps a completion file of your own' test -f "$bashc"
