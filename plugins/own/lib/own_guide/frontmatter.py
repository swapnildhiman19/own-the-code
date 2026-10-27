"""A tiny reader and writer for the header at the top of a flow page (no PyYAML needed).

    ---
    flow: who-am-i
    checked_commit: 3f2a9c1
    files: [app/routes/checkout.py, app/cart.py]
    hashes: [app/routes/checkout.py=9daeafb9864cf43055ae93beb0afd6c7d144bfa4, ...]
    ---

Supports `key: value`, inline lists `[a, b]`, and block lists (`key:` then `- item` lines).
"""

from __future__ import annotations

from typing import Any


def _clean(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return value


def split(text: str) -> tuple[dict[str, Any], str, bool]:
    """(header values, the text after the header, whether a header was found)."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text, False
    meta: dict[str, Any] = {}
    current_list: list[str] | None = None
    for index, raw in enumerate(lines[1:], start=1):
        line = raw.rstrip("\r\n").rstrip()
        if line.strip() == "---":
            return meta, "".join(lines[index + 1:]), True
        stripped = line.strip()
        if current_list is not None and stripped.startswith("- "):
            current_list.append(_clean(stripped[2:]))
            continue
        current_list = None
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not value:
            current_list = []
            meta[key] = current_list
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key] = [_clean(v) for v in inner.split(",") if v.strip()] if inner else []
        else:
            meta[key] = _clean(value)
    return {}, text, False  # no closing '---': not a header


def parse(text: str) -> dict[str, Any]:
    return split(text)[0]


def dump(meta: dict[str, Any]) -> str:
    out = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            out.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        else:
            out.append(f"{key}: {value}")
    out.append("---")
    return "\n".join(out) + "\n"


def update(text: str, changes: dict[str, Any]) -> str:
    """Return `text` with its header values changed (existing keys keep their order)."""
    meta, body, _found = split(text)
    meta.update(changes)
    return dump(meta) + body
