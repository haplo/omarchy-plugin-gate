# Changelog

All notable changes to omarchy-plugin-gate. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-10-28

### Added

- `approve <name>`: a one-time human approval for a candidate the gate held
  back. It prints the verdict, structural results and patch path, asks for a
  reason (an empty one is allowed; `--reason` skips the prompt), then moves
  `gate-approved`. The waiver is written to `waived/<sha>` with the date, user,
  reason, base commit and patch blob hash; the failed verdict is kept. Supports
  `--sha`, `--show` and `-n`/`--dry-run`. `status` reports waived approvals,
  `update` accepts a waiver in place of a review marker, and there is a
  `mise run approve` task.
- Structural findings: checks that often fire on legitimate code no longer fail
  the review on their own. Protected paths, binaries outside common asset
  types, executables without a shebang, manifest `kinds`/`entryPoints` changes,
  and download-and-execute lines are now numbered findings (`F1`, `F2`, …)
  handed to the reviewer with the patch, recorded in
  `reviews/<short-sha>/findings.txt`.
- The reviewer must answer each finding with exactly one
  `Fn CLEARED <reason>` line. A `REVIEW PASS` with a finding unanswered,
  answered twice, `CONFIRMED`, cleared without a reason, or an answer to a
  finding that does not exist is recorded as `REVIEW FAIL`.
- Passes that cleared findings write `reviews/<short-sha>/cleared` with each
  finding and the reviewer's reason. `check`, `status`, `add`, the log and the
  notification all call them out.
- More than 40 findings in one candidate is a hard failure.
- The reviewer must prove it saw the whole patch. The copy it receives,
  `reviews/<short-sha>/patch.review`, ends with a line carrying a random code
  word generated for each run and kept out of the prompt; the reviewer must
  answer `SEEN <word>`. A `REVIEW PASS` without the right word is recorded as
  `REVIEW FAIL`, and a `REVIEW FAIL` without it says the reviewer never saw
  the whole patch.
- A patch that is not valid UTF-8 is a hard structural failure naming the
  offending files. OpenCode does not hand such a file to the model as text, so
  the reviewer used to see no code at all and blame the patch size.
- `doctor` reports an installed reviewer agent that differs from the one in the
  repository.

### Changed

- The default gate root (`OMARCHY_PLUGIN_GATE_ROOT`) is now
  `~/Work/omarchy-plugins/`.
- Hard structural failures, which still skip the model, are now limited to an
  oversized patch, a patch that is not valid UTF-8, a manifest `id` change or
  unreadable manifest, a manifest that does not validate, entry points that
  escape the plugin directory or name a missing file, and too many findings.
- The default `OMARCHY_PLUGIN_GATE_MAX_PATCH` is now 2 MiB (was 512 KiB),
  sized for a reviewer model with a 1M-token context. Set it lower for smaller
  models.
- The `plugin-reviewer` agent has a section on judging findings and a new output
  format, and is installed verbatim; the state path is no longer rendered into
  it. Re-run `mise run install`.
- The reviewer runs from the candidate's review directory instead of the whole
  state directory, and may read, glob and grep only there. It gets 40 steps
  (was 8) and is told to page through `./patch.review` if the attachment is
  missing or cut off.

### Fixed

- The reviewer's `read`, `glob` and `grep` permissions never matched anything:
  OpenCode V2 matches `read` against a path relative to the working directory
  and `glob`/`grep` against the pattern, not an absolute state path. Every tool
  call was denied, so a reviewer that could not use the attachment had no way
  to read the patch.
- The entry-point "missing file" check and `omarchy plugin validate` now
  inspect the candidate commit rather than the clone's checkout. Before, a new
  entry-point file was always reported missing and the manifest was validated at
  the wrong revision.
- The entry-point escape check matches `..` path segments only, so a name such
  as `foo..qml` is no longer flagged.

## [0.1.0] - 2026-10-27

Initial release.

### Added

- `omarchy-plugin-gate` with `add`, `check`, `update`, `status` and `doctor`.
  Upstream changes are fetched into a clone under `~/Code/omarchy-plugins/`,
  reviewed, and staged on `refs/heads/gate-approved`. The installed copy's
  origin is the clone, so `omarchy plugin update` can only reach approved
  commits.
- Structural pre-checks with no model involved: protected paths, unexpected
  binaries, executables without a shebang, manifest identity changes, entry
  points, manifest validation, download-and-execute lines, and a patch size
  limit.
- A read-only `plugin-reviewer` OpenCode agent that is deny-by-default, runs
  from the state directory, and fails closed on a crash, timeout or missing
  verdict.
- An evidence trail under `~/.local/state/omarchy-plugin-gate/<name>/`.
- A `post-merge` tripwire that reviews out-of-band upstream merges and rolls
  them back, leaving local commits alone.
- A nightly systemd user timer for `check`, desktop notifications, mise tasks,
  install and uninstall scripts, and a fixture test suite.

[0.2.0]: https://github.com/haplo/omarchy-plugin-gate/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/haplo/omarchy-plugin-gate/releases/tag/v0.1.0
