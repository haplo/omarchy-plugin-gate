# omarchy-plugin-gate

Review-before-update gate for [Omarchy](https://omarchy.org) shell plugins.

Omarchy plugins are unsandboxed code inside the long-lived `omarchy-shell`
process. `omarchy plugin update` fast-forwards them from GitHub, which means an
upstream commit is a code change to a process that already holds your session.
This gate puts a review step in front of that: upstream changes are fetched and
reviewed in a clone you own, and the installed plugin can only move to a commit
that passed.

## Requirements

- Omarchy with the `omarchy` command
- `git`, `jq`, `bash`
- [OpenCode](https://opencode.ai) on `PATH` (the reviewer runs headlessly)

## Install

```sh
git clone https://github.com/haplo/omarchy-plugin-gate ~/Code/omarchy-plugin-gate
cd ~/Code/omarchy-plugin-gate
mise trust          # once: allow mise to run this project's tasks
mise run install
```

`mise run install` symlinks the command to `~/.local/bin`, renders the reviewer
agent into `~/.config/opencode/agents/`, installs the systemd user units and
enables the nightly check. Use `mise run install:no-timer` to skip the timer.

Without mise, `scripts/install.sh` does the same thing.

Then wire up whatever is already cloned:

```sh
omarchy-plugin-gate doctor --fix
```

## Quick start

```sh
# install a new plugin end to end: clone, review, install disabled, enable on PASS
omarchy-plugin-gate add https://github.com/ninepointlabs/omasync

# review upstream changes (the daily timer runs this)
omarchy-plugin-gate check

# after reading a failed review yourself, accept that one commit
omarchy-plugin-gate approve <name>

# apply approved commits to the installed copies
omarchy-plugin-gate update

# what is installed, approved, upstream, held
omarchy-plugin-gate status
```

A notification appears only when something needs a decision: an update is ready
to install, or a review was held back. A successful `update` closes it.

## How it works

```
~/Code/omarchy-plugins/<name>/     normal clone, origin = upstream
  main                             your checkout, safe to branch and push from
  refs/heads/gate-approved         exactly what passed review or was waived

~/.config/omarchy/plugins/<id>/    installed copy, origin = the clone above
```

Because the installed copy fetches from the clone, plain `omarchy plugin update`
can only ever pull `main` from that clone — which is either approved or your own
work. `check` fetches upstream, diffs `gate-approved..origin/<branch>`, reviews
it, and advances `gate-approved` only on `REVIEW PASS` or a recorded one-time
waiver. `update` then fast-forwards the installed copy to that ref, validates
the manifest, and asks the shell to rescan.

Every candidate keeps its evidence under
`~/.local/state/omarchy-plugin-gate/<name>/`:

```
reviews/<short-sha>/patch        the exact diff that was reviewed
reviews/<short-sha>/mech.txt     structural pre-check results
reviews/<short-sha>/hints.txt    keywords handed to the reviewer
reviews/<short-sha>/review.txt   the reviewer's full output
reviews/<short-sha>/verdict      REVIEW PASS/FAIL plus reasons
reviewed/<sha>                   approvals that came from a REVIEW PASS
waived/<sha>                     one-time human approvals (verdict kept)
held                             the last commit that failed and why
```

## Two layers of review

**Structural checks** run first, with no model involved. Any of these is an
immediate `REVIEW FAIL`:

- binary files outside common asset types
- `.git/`, `.ssh/`, `authorized_keys`, `sudoers`, `systemd/`, `omarchy/hooks`,
  `.config/`, `*.service`, `*.timer`, `*.desktop`, `*.pem`, `*.key`
- newly executable files without a shebang
- manifest `id`, `kinds` or `entryPoints` changes
- entry points that escape the plugin directory or point at missing files
- `manifest.json` that does not validate
- added code lines that pipe a download or decoder into a shell, use `/dev/tcp`,
  or pipe into `sudo`/`pkexec`
- diffs larger than `OMARCHY_PLUGIN_GATE_MAX_PATCH` (default 512 KiB)

Anything larger goes to a human instead of an automatic pass.

**The reviewer** is a read-only OpenCode agent (`plugin-reviewer`) with no shell,
no write access and no network tools; it may only read the gate's state
directory. It receives the patch plus keyword hints and must answer on the first
line with exactly `REVIEW PASS` or `REVIEW FAIL`, followed by one reason per
line. It never runs from the plugin checkout, so a hostile `.opencode/`
configuration in the diff cannot execute. Reviewer crash, timeout, or a missing
verdict line all fail closed.

## Approving a failed review

`approve` is the deliberate escape hatch. It never guesses: without `--sha` it
takes the commit named in `held`, prints the verdict, structural findings, and
patch path, then asks for a reason. The reason may be empty; `--reason TEXT`
skips the prompt, which is also required when stdin is not a terminal. With
`--show` it prints the patch before asking, and `-n` / `--dry-run` shows the
decision without changing anything.

```sh
omarchy-plugin-gate approve my-plugin          # prompt for a reason
omarchy-plugin-gate approve my-plugin --show   # read the diff first
omarchy-plugin-gate approve my-plugin --reason "upstream fix I checked"
omarchy-plugin-gate update -p my-plugin
```

A waiver is one commit, not a standing trust setting. It lives in
`waived/<sha>` with the date, user, reason, base commit, and the blob hash of
the patch that was on screen. The failed verdict is left untouched, so `status`
shows both `REVIEW FAIL` and `approval waived by hand`. `approve` moves
`gate-approved` and installs the hooks; `update` still does the installation.

Approval covers the held candidate only. It does not fetch, and `--sha` must
name a commit that is still reachable from `origin/<branch>`. Structural holds
can be waived too: the findings are printed first, so read them before you
answer.

## Tripwire

`doctor --fix` installs a `post-merge` hook in both the clone and the installed
copy. If a merge did not come through the gate (a manual `git pull`, say), the
hook reviews the incoming commits and, on failure, resets them and disables the
plugin. Commits you authored yourself are never reviewed or rolled back.

This is a net, not the main gate: `omarchy-shell` may already have rescanned by
the time a hook finishes. The gate is what prevents bad code from arriving.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `OMARCHY_PLUGIN_GATE_ROOT` | `~/Code/omarchy-plugins` | where working clones live |
| `OMARCHY_PLUGIN_GATE_MODEL` | OpenCode's default | model for the reviewer, e.g. `venice/claude-opus-4-7` |
| `OMARCHY_PLUGIN_GATE_NOTIFY` | `all` | `all`, `ready`, or `none` |
| `OMARCHY_PLUGIN_GATE_TIMEOUT` | `420` | reviewer timeout, seconds |
| `OMARCHY_PLUGIN_GATE_MAX_PATCH` | `524288` | largest diff that is auto-reviewed |
| `OMARCHY_PLUGIN_GATE_STATE` | `~/.local/state/omarchy-plugin-gate` | evidence and markers |

`OMARCHY_PLUGIN_GATE_STATE` is rendered into the reviewer agent at install time;
re-run `mise run install` after changing it.

## Already-installed plugins

`add` refuses an id that is already installed. To adopt one that Omarchy
installed from GitHub:

```sh
git clone <upstream-url> ~/Code/omarchy-plugins/<name>
git -C ~/.config/omarchy/plugins/<id> remote set-url origin ~/Code/omarchy-plugins/<name>
omarchy-plugin-gate check        # reviews the current tree, sets gate-approved
omarchy-plugin-gate doctor --fix # tripwires
```

`check` bootstraps the first review from the whole tree when no
`gate-approved` exists yet.

## Tests

```sh
mise run test     # or: tests/run
```

The suite builds throwaway repositories in a temporary directory, uses a stub
reviewer and stub `omarchy` commands, and covers the bootstrap review, clean and
partial updates, every structural rejection (asserting the model is *not*
called), reviewer failure and crash, update applying and refusing, the tripwire
rolling back a rejected pull while leaving local commits alone, notification
policy, one-time approvals (including dry run, `--sha`, `--show`, and the
resulting update), and both `add` outcomes. No network, no real plugin install.

## Uninstall

```sh
mise run uninstall
```

Removes the command, reviewer agent, units and the tripwires. Working clones,
review evidence and installed plugins are kept; the output explains how to point
the installed copies back at their upstream repositories.

## Limits, honestly

- The reviewer is advisory. The structural checks and the retained patch and
  transcript for every approved commit are the durable record. Read a diff
  yourself when the gate says `REVIEW FAIL` — use `approve --show` or the patch
  path in `status`.
- `origin/main` in a working clone is whatever upstream last published; the gate
  only governs what the installed plugin sees. Anyone with write access to this
  machine can move `gate-approved` by hand.
- Plugins still run unsandboxed. This gate makes updates reviewable; it does not
  sandbox the plugin.

## License

[MIT](LICENSE).
