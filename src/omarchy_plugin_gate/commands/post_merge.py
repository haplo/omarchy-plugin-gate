"""_post-merge: the tripwire's entry point, run by the hook after a merge."""

from pathlib import Path

from ..context import Context
from ..git import Repo
from ..hooks import is_upstream_commit
from ..notify import notify
from ..plugins import plugin_for_dir, same_path
from ..review import review
from . import disable_plugin


def run(ctx: Context, directory: str) -> int:
    if not directory or not Path(directory).is_dir():
        return 0
    target = Path(directory)
    repo = Repo(target)
    if not repo.is_repo():
        return 0

    new = repo.head()
    old = repo.rev("ORIG_HEAD")
    if not new or not old or new == old:
        return 0

    name = plugin_for_dir(ctx.cfg, target)
    if not name or ctx.state.has_approval(name, new):
        return 0

    clone = ctx.clone(name)
    if not is_upstream_commit(clone, new):
        return 0

    ctx.state.log_event(name, f"hook: reviewing out-of-band merge {old}..{new} in {target}")
    if review(ctx, name, clone, old, new):
        ctx.state.set_marker(name, new, "hook review")
        return 0

    repo.ok("reset", "--hard", "--quiet", old)
    plugin_id = ctx.manifest_id(name)
    if plugin_id and same_path(target, ctx.cfg.installed_root / plugin_id):
        disable_plugin(plugin_id)
    ctx.state.log_event(name, f"hook: rolled back {new}")
    notify(
        ctx,
        f"{name}: update rolled back",
        f"The review failed, so {new} was reverted and the plugin disabled.",
    )
    return 1
