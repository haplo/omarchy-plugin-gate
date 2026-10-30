#!/usr/bin/env bash
# Remove what install.sh added. Config, state, evidence and working clones are
# kept.
set -euo pipefail

REPO=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)

BIN_DIR=${OMARCHY_PLUGIN_GATE_BIN_DIR:-$HOME/.local/bin}
CONFIG_HOME=${XDG_CONFIG_HOME:-}
[[ $CONFIG_HOME == /* ]] || CONFIG_HOME=$HOME/.config
DATA_HOME=${XDG_DATA_HOME:-}
[[ $DATA_HOME == /* ]] || DATA_HOME=$HOME/.local/share
CONFIG_FILE=$CONFIG_HOME/omarchy-plugin-gate/config.toml
# The root and state may be set in the config file, so ask the gate. If it
# cannot say (a broken config, say), fall back to the environment.
if paths=$(python3 -I "$REPO/scripts/paths.py"); then
  ROOT=$(sed -n 1p <<<"$paths")
  STATE_DIR=$(sed -n 2p <<<"$paths")
else
  echo "uninstall: using the environment and default paths instead" >&2
  ROOT=${OMARCHY_PLUGIN_GATE_ROOT:-$HOME/Work/omarchy-plugins}
  STATE_DIR=${OMARCHY_PLUGIN_GATE_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/omarchy-plugin-gate}
fi
UNIT_DIR=$CONFIG_HOME/systemd/user
AGENT_FILE=$CONFIG_HOME/opencode/agents/plugin-reviewer.md
BASH_COMPLETION_DIR=$DATA_HOME/bash-completion/completions
FISH_COMPLETION_DIR=$DATA_HOME/fish/vendor_completions.d
ZSH_COMPLETION_DIR=$DATA_HOME/zsh/site-functions

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now omarchy-plugin-gate-check.timer >/dev/null 2>&1 || true
fi
rm -f "$UNIT_DIR/omarchy-plugin-gate-check.service" "$UNIT_DIR/omarchy-plugin-gate-check.timer"
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

if [[ -L $BIN_DIR/omarchy-plugin-gate ]]; then
  target=$(readlink -f "$BIN_DIR/omarchy-plugin-gate" 2>/dev/null || true)
  if [[ $target == "$REPO/bin/omarchy-plugin-gate" ]]; then
    rm -f "$BIN_DIR/omarchy-plugin-gate"
    echo "removed $BIN_DIR/omarchy-plugin-gate"
  fi
fi

if [[ -f $AGENT_FILE ]] && grep -q 'Reviews an Omarchy shell plugin diff' "$AGENT_FILE"; then
  rm -f "$AGENT_FILE"
  echo "removed $AGENT_FILE"
fi

# Only links into this repository: a completion file of the user's own stays.
remove_completion() { # <path>
  local target
  [[ -L $1 ]] || return 0
  target=$(readlink -f "$1" 2>/dev/null || true)
  if [[ $target == "$REPO/completions/"* ]]; then
    rm -f "$1"
    echo "removed $1"
  fi
}

remove_completion "$BASH_COMPLETION_DIR/omarchy-plugin-gate"
remove_completion "$FISH_COMPLETION_DIR/omarchy-plugin-gate.fish"
remove_completion "$ZSH_COMPLETION_DIR/_omarchy-plugin-gate"

remove_hooks() {
  local base=$1 dir hp hook
  [[ -d $base ]] || return 0
  for dir in "$base"/*/; do
    [[ -d $dir/.git ]] || continue
    hp=$(git -C "$dir" rev-parse --git-path hooks 2>/dev/null) || continue
    [[ $hp == /* ]] || hp="$dir/$hp"
    hook=$hp/post-merge
    if [[ -f $hook ]] && grep -q 'omarchy-plugin-gate' "$hook" 2>/dev/null; then
      rm -f "$hook"
      echo "removed hook $hook"
    fi
  done
}

remove_hooks "$ROOT"
remove_hooks "$CONFIG_HOME/omarchy/plugins"

cat <<EOF

Removed the command, reviewer agent, completions and timer.

Kept on purpose:
  config           $CONFIG_FILE
  working clones   $ROOT
  review evidence  $STATE_DIR
  installed plugins (they still track the clones above; point their origin back
  at the upstream repository with 'git remote set-url' if you want plain
  'omarchy plugin update' to follow GitHub again)
EOF
