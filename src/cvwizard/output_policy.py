"""Guard private CLI outputs against accidental commits."""

from __future__ import annotations

import subprocess
from pathlib import Path


PRIVATE_DIRECTORIES = (
    ("data", "private"), ("generated",), ("outputs",),
    ("applications",), ("tmp",), ("work",),
)


def _git_root(path: Path) -> Path | None:
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            return parent
    return None


def private_output_path(path: Path, private_root: Path | None = None) -> Path:
    """Return a resolved safe destination or raise a clear policy error.

    Outside a Git tree, an explicit absolute private root is required. Within a
    Git tree, only the repository's established ignored output directories work.
    Resolving first prevents a symlink from disguising a tracked destination.
    """
    target = path.expanduser().resolve()
    repo = _git_root(target.parent)
    if repo is not None:
        relative = target.relative_to(repo).parts
        if any(relative[:len(prefix)] == prefix and len(relative) > len(prefix) for prefix in PRIVATE_DIRECTORIES):
            try:
                ignored = subprocess.run(
                    ["git", "-C", str(repo), "check-ignore", "-q", "--", str(target)],
                    check=False, capture_output=True,
                ).returncode == 0
            except OSError:
                ignored = False
            if ignored:
                return target
            raise ValueError(f"output directory is not Git-ignored: {target}")
        raise ValueError(f"unsafe output path inside Git worktree: {target}; use data/private/ or an ignored output directory")
    if private_root is None:
        raise ValueError(f"output outside a Git worktree requires --private-output-root: {target}")
    if not private_root.is_absolute():
        raise ValueError("--private-output-root must be an absolute path")
    root = private_root.expanduser().resolve()
    if _git_root(root) is not None:
        raise ValueError("--private-output-root must be outside every Git worktree")
    if not target.is_relative_to(root) or target == root:
        raise ValueError(f"output is outside configured private root: {target}")
    return target
