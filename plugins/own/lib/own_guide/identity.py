"""Which guide does this folder belong to? One repo = exactly one guide.

A project is recognised by its GitHub (or other) address, cleaned so that
`git@github.com:Acme/API.git` and `https://github.com/acme/api` are the same thing.
A repo with no address is recognised by its main folder - the same for every worktree,
the way Claude Code's own memory works. `~/code-guides/projects.json` remembers every
address and main folder seen for each guide, so a remote added later or a renamed repo
still lands in the same guide. When a match is genuinely unclear, the answer is
"ambiguous" and the user is asked once; a second guide is never created silently.
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Any

from . import state
from .gitinfo import git

_SCP_LIKE = re.compile(r"^(?:[\w.+-]+@)?([\w.-]+):(.+)$")
_RESERVED = {"_knowledge"}


def normalize_remote(url: str) -> str | None:
    """`git@github.com:Owner/Repo.git` -> `github.com/owner/repo`. Local paths -> None."""
    url = (url or "").strip()
    if not url or url.startswith(("/", ".", "~", "file:")):
        return None
    if "://" in url:
        parts = urllib.parse.urlsplit(url)
        if not parts.hostname:
            return None
        host, path = parts.hostname, parts.path
    else:
        match = _SCP_LIKE.match(url)
        if not match:
            return None
        host, path = match.group(1), match.group(2)
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    path = path.strip("/")
    return f"{host.lower()}/{path.lower()}" if path else None


def repo_info(cwd: str | Path) -> dict[str, Any] | None:
    """The repo's address and main folder, or None outside a git repo."""
    top = git(["rev-parse", "--show-toplevel"], cwd)
    if top.code != 0:
        return None
    # Plain --git-common-dir (works on git older than 2.31); a relative answer is relative to cwd.
    common = git(["rev-parse", "--git-common-dir"], cwd)
    if common.code != 0:
        return None
    common_dir = (Path(cwd) / common.out.strip()).resolve()
    main_root = common_dir.parent if common_dir.name == ".git" else common_dir

    remote = None
    origin = git(["remote", "get-url", "origin"], cwd)
    if origin.code == 0:
        remote = normalize_remote(origin.out)
    else:
        names = git(["remote"], cwd)
        first = names.out.split()[0] if names.code == 0 and names.out.split() else None
        if first:
            other = git(["remote", "get-url", first], cwd)
            remote = normalize_remote(other.out) if other.code == 0 else None

    main_root_str = str(main_root)
    return {
        "toplevel": str(Path(top.out.strip()).resolve()),
        "main_root": main_root_str,
        "remote": remote,
        "id": remote or f"root:{main_root_str}",
    }


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "project"


def _repo_name(info_or_entry: dict[str, Any]) -> str:
    remotes = info_or_entry.get("remotes") or ([info_or_entry["remote"]] if info_or_entry.get("remote") else [])
    if remotes:
        return slug(remotes[0].rsplit("/", 1)[-1])
    roots = info_or_entry.get("roots") or [info_or_entry.get("main_root", "")]
    return slug(Path(roots[0]).name)


def _registry_path() -> Path:
    return state.guides_root() / "projects.json"


def _match(registry: dict[str, Any], info: dict[str, Any]) -> dict[str, Any] | None:
    for entry in registry["projects"]:
        if info["remote"] and info["remote"] in entry.get("remotes", []):
            return entry
    for entry in registry["projects"]:
        if info["main_root"] in entry.get("roots", []) or entry.get("id") == info["id"]:
            return entry
    return None


def _ambiguous_candidate(registry: dict[str, Any], info: dict[str, Any]) -> dict[str, Any] | None:
    """Same repo name, and one side has no address: can't tell if it's the same project."""
    name = _repo_name(info)
    for entry in registry["projects"]:
        if _repo_name(entry) == name and (not info["remote"] or not entry.get("remotes")):
            return entry
    return None


def _pick_folder(info: dict[str, Any], registry: dict[str, Any]) -> str:
    taken = {e["folder"] for e in registry["projects"]} | _RESERVED
    root = state.guides_root()
    if root.is_dir():
        taken |= {p.name for p in root.iterdir() if p.is_dir()}
    repo = _repo_name(info)
    candidates = [repo]
    if info["remote"]:
        parts = info["remote"].split("/")
        if len(parts) >= 3:
            candidates.append(f"{slug(parts[-2])}-{repo}")
    for candidate in candidates:
        if candidate not in taken:
            return candidate
    n = 2
    while f"{repo}-{n}" in taken:
        n += 1
    return f"{repo}-{n}"


def _remember(entry: dict[str, Any], info: dict[str, Any]) -> bool:
    changed = False
    if info["remote"] and info["remote"] not in entry.setdefault("remotes", []):
        entry["remotes"].append(info["remote"])
        changed = True
    if info["main_root"] not in entry.setdefault("roots", []):
        entry["roots"].append(info["main_root"])
        changed = True
    return changed


def resolve(cwd: str | Path, create: bool = True) -> dict[str, Any] | None:
    """Find (or create) the guide for this folder.

    Returns None outside git, else {"status": known|new|ambiguous|unregistered,
    "entry": {...} (not for ambiguous/unregistered), "candidate": {...} (ambiguous), "info": {...}}.
    """
    info = repo_info(cwd)
    if info is None:
        return None
    path = _registry_path()
    with state.locked(path):
        registry = state.read_json(path, {"projects": []})
        entry = _match(registry, info)
        if entry is not None:
            if _remember(entry, info):
                state.write_json(path, registry)
            return {"status": "known", "entry": entry, "info": info}
        candidate = _ambiguous_candidate(registry, info)
        if candidate is not None:
            return {"status": "ambiguous", "candidate": candidate, "info": info}
        if not create:
            return {"status": "unregistered", "info": info}
        entry = _new_entry(registry, info)
        state.write_json(path, registry)
    return {"status": "new", "entry": entry, "info": info}


def _new_entry(registry: dict[str, Any], info: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "id": info["id"],
        "folder": _pick_folder(info, registry),
        "remotes": [info["remote"]] if info["remote"] else [],
        "roots": [info["main_root"]],
    }
    registry["projects"].append(entry)
    state.project_dir(entry["folder"]).mkdir(parents=True, exist_ok=True)
    return entry


def link(cwd: str | Path, folder: str) -> dict[str, Any]:
    """The user said "yes, same project": attach this repo to the guide in `folder`."""
    info = repo_info(cwd)
    if info is None:
        raise ValueError("not inside a git repository")
    path = _registry_path()
    with state.locked(path):
        registry = state.read_json(path, {"projects": []})
        entry = next((e for e in registry["projects"] if e["folder"] == folder), None)
        if entry is None:
            raise ValueError(f"no guide named {folder!r}")
        _remember(entry, info)
        state.write_json(path, registry)
    return entry


def register_new(cwd: str | Path) -> dict[str, Any]:
    """The user said "no, a different project": give this repo its own guide."""
    info = repo_info(cwd)
    if info is None:
        raise ValueError("not inside a git repository")
    path = _registry_path()
    with state.locked(path):
        registry = state.read_json(path, {"projects": []})
        existing = _match(registry, info)
        if existing is not None:
            return existing
        entry = _new_entry(registry, info)
        state.write_json(path, registry)
    return entry


def all_projects() -> list[dict[str, Any]]:
    return state.read_json(_registry_path(), {"projects": []})["projects"]
