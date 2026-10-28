#!/usr/bin/env bash
# Install omarchy-plugin-gate for the current user.
#
# Symlinks the command into ~/.local/bin, installs the reviewer agent and the
# systemd user units, and enables the nightly
# check. Idempotent: run it again after pulling changes.

set -euo pipefail

REPO=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)

BIN_DIR=${OMARCHY_PLUGIN_GATE_BIN_DIR:-$HOME/.local/bin}
CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
STATE_DIR=${OMARCHY_PLUGIN_GATE_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/omarchy-plugin-gate}
UNIT_DIR=$CONFIG_HOME/systemd/user
AGENT_FILE=$CONFIG_HOME/opencode/agents/plugin-reviewer.md
ENABLE_TIMER=1

usage() {
  cat <<'EOF'
Install omarchy-plugin-gate for the current user.

Usage: scripts/install.sh [--no-timer]

  --no-timer   install the command and agent, but do not enable the nightly check

Environment:
  OMARCHY_PLUGIN_GATE_BIN_DIR   where to link the command (default ~/.local/bin)
  OMARCHY_PLUGIN_GATE_STATE     state directory (default ~/.local/state/omarchy-plugin-gate)
  XDG_CONFIG_HOME               config root (default ~/.config)
EOF
}

while (($# > 0)); do
  case $1 in
  --no-timer) ENABLE_TIMER=0; shift ;;
  -h | --help) usage; exit 0 ;;
  *)
    echo "install: unknown option: $1" >&2
    exit 1
    ;;
  esac
done

command -v git >/dev/null 2>&1 || { echo "install: git is required" >&2; exit 1; }
[[ -f $REPO/bin/omarchy-plugin-gate ]] || { echo "install: missing $REPO/bin/omarchy-plugin-gate" >&2; exit 1; }

mkdir -p "$BIN_DIR" "$STATE_DIR" "$UNIT_DIR" "$(dirname "$AGENT_FILE")"

if [[ -e $BIN_DIR/omarchy-plugin-gate && ! -L $BIN_DIR/omarchy-plugin-gate ]]; then
  echo "install: replacing the existing copy at $BIN_DIR/omarchy-plugin-gate"
fi
chmod 755 "$REPO/bin/omarchy-plugin-gate"
ln -sfn "$REPO/bin/omarchy-plugin-gate" "$BIN_DIR/omarchy-plugin-gate"

# The agent's scope comes from the directory the gate runs it in, so the
# template is installed as is. Re-run this script after changing it.
cp "$REPO/agents/plugin-reviewer.md.in" "$AGENT_FILE"

for unit in omarchy-plugin-gate-check.service omarchy-plugin-gate-check.timer; do
  sed "s#%h/.local/bin/omarchy-plugin-gate#$BIN_DIR/omarchy-plugin-gate#g" \
    "$REPO/systemd/$unit" >"$UNIT_DIR/$unit"
done

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  if ((ENABLE_TIMER)); then
    systemctl --user enable --now omarchy-plugin-gate-check.timer
  fi
fi

cat <<EOF

omarchy-plugin-gate installed

  command   $BIN_DIR/omarchy-plugin-gate -> $REPO/bin/omarchy-plugin-gate
  reviewer  $AGENT_FILE
  units     $UNIT_DIR/omarchy-plugin-gate-check.{service,timer}
  state     $STATE_DIR

Next:
  omarchy-plugin-gate doctor --fix      # add the review tripwire to existing clones
  omarchy-plugin-gate add <git-url>     # gate a new plugin
  omarchy-plugin-gate check             # review what is already cloned

Optional, for a stronger reviewer model:
  export OMARCHY_PLUGIN_GATE_MODEL=venice/<model>
  and uncomment the Environment= line in the service so the nightly run uses it.
EOF
