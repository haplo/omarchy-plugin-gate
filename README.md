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
git clone https://github.com/haplo/omarchy-plugin-gate ~/Work/omarchy-plugin-gate
cd ~/Work/omarchy-plugin-gate
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
~/Work/omarchy-plugins/<name>/     normal clone, origin = upstream
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
reviews/<short-sha>/patch.review the copy handed to the reviewer (patch + code word)
reviews/<short-sha>/mech.txt     hard structural check results
reviews/<short-sha>/findings.txt structural findings handed to the reviewer
reviews/<short-sha>/hints.txt    keywords handed to the reviewer
reviews/<short-sha>/review.txt   the reviewer's full output
reviews/<short-sha>/verdict      REVIEW PASS/FAIL plus reasons
reviews/<short-sha>/cleared      findings the reviewer cleared, and why
reviewed/<sha>                   approvals that came from a REVIEW PASS
waived/<sha>                     one-time human approvals (verdict kept)
held                             the last commit that failed and why
```

## Two layers of review

**Structural checks** run first, with no model involved, in two tiers.

*Hard failures* are an immediate `REVIEW FAIL`; the reviewer is never called:

- diffs larger than `OMARCHY_PLUGIN_GATE_MAX_PATCH` (default 2 MiB, sized for a
  reviewer model with a 1M-token context), which the reviewer could not read in
  full
- diffs that are not valid UTF-8, which OpenCode would not hand to the reviewer
  as text; the offending files are named
- a manifest `id` change, or a manifest that can no longer be read
- `manifest.json` that does not validate at the candidate commit
- entry points that escape the plugin directory or name a file missing from the
  candidate commit
- more than 40 structural findings in one candidate

*Findings* are pattern matches that usually, but not always, mean trouble. They
are numbered `F1`, `F2`, … and handed to the reviewer with the patch:

- binary files outside common asset types
- `.git/`, `.ssh/`, `authorized_keys`, `sudoers`, `systemd/`, `omarchy/hooks`,
  `*.service`, `*.timer`, `*.socket`, `*.path`, `*.desktop`, `*.pem`, `*.key`,
  `*.p12`
- newly executable files without a shebang, or in one of the paths above
- manifest `kinds` or `entryPoints` changes
- added code lines that pipe a download or decoder into a shell, use `/dev/tcp`,
  or pipe into `sudo`/`pkexec`

The reviewer must answer every finding, on its own line after the verdict:

```
REVIEW PASS
F1 CLEARED systemd/ holds QML that displays unit status; nothing is installed
F2 CLEARED icon.bin is loaded by Icon.qml as image data
```

A `REVIEW PASS` with a finding left unanswered, answered twice, answered
`CONFIRMED`, cleared without a reason, or with an answer to a finding that does
not exist is recorded as `REVIEW FAIL`. A pass that cleared findings writes
`reviews/<short-sha>/cleared`, and `check`, `status` and the notification all
say so, so you know which approvals are worth a second look.

**The reviewer** is a read-only OpenCode agent (`plugin-reviewer`) with no shell,
no write access and no network tools. It runs from the candidate's review
directory and may only read, glob and grep inside it, so it sees the patch and
nothing else. It receives the patch, the structural findings and keyword hints,
and must answer on the first line with exactly `REVIEW PASS` or `REVIEW FAIL`,
followed by its finding answers and one reason per line. It never runs from the
plugin checkout, so a hostile `.opencode/` configuration in the diff cannot
execute. Reviewer crash, timeout, or a missing verdict line all fail closed.

The copy of the patch the reviewer gets (`patch.review`) ends with a line
carrying a random code word, generated for each run and never put in the prompt.
The reviewer must finish its answer with `SEEN <word>`. Without the right word
the verdict is `REVIEW FAIL`: the reviewer did not receive, or did not finish,
the whole patch, so whatever it said was not about all of the code. If the
attachment arrives cut off, the reviewer can page through `./patch.review` with
its read tool.

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
name a commit that is still reachable from `origin/<branch>`. Hard structural
failures can be waived too: the failures and findings are printed first, so read
them before you answer.

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
| `OMARCHY_PLUGIN_GATE_ROOT` | `~/Work/omarchy-plugins` | where working clones live |
| `OMARCHY_PLUGIN_GATE_MODEL` | OpenCode's default | model for the reviewer, e.g. `venice/claude-opus-4-7` |
| `OMARCHY_PLUGIN_GATE_NOTIFY` | `all` | `all`, `ready`, or `none` |
| `OMARCHY_PLUGIN_GATE_TIMEOUT` | `420` | reviewer timeout, seconds |
| `OMARCHY_PLUGIN_GATE_MAX_PATCH` | `2097152` | largest diff that is auto-reviewed; assumes a 1M-token model, so lower it for smaller ones (about 3 bytes per token, minus headroom) |
| `OMARCHY_PLUGIN_GATE_STATE` | `~/.local/state/omarchy-plugin-gate` | evidence and markers |

Re-run `mise run install` after pulling a change to the reviewer agent;
`doctor` reports an installed agent that no longer matches the repository.

## Already-installed plugins

`add` refuses an id that is already installed. To adopt one that Omarchy
installed from GitHub:

```sh
git clone <upstream-url> ~/Work/omarchy-plugins/<name>
git -C ~/.config/omarchy/plugins/<id> remote set-url origin ~/Work/omarchy-plugins/<name>
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
partial updates, every hard structural failure (asserting the model is *not*
called), every kind of structural finding reaching the reviewer, each way a
reviewer can fail to clear a finding, a missing, wrong or planted code word,
reviewer failure and crash, the reviewer's working directory, `doctor`
spotting a stale reviewer agent, update applying and refusing, the tripwire
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

- The reviewer is advisory. The hard structural checks and the retained patch
  and transcript for every approved commit are the durable record. Findings the
  reviewer cleared are a judgement call a hostile diff may try to argue it
  into; `cleared` lists them, so check those approvals first. Read a diff
  yourself when the gate says `REVIEW FAIL` — use `approve --show` or the patch
  path in `status`.
- `origin/main` in a working clone is whatever upstream last published; the gate
  only governs what the installed plugin sees. Anyone with write access to this
  machine can move `gate-approved` by hand.
- Plugins still run unsandboxed. This gate makes updates reviewable; it does not
  sandbox the plugin.

## License

[MIT](LICENSE).
