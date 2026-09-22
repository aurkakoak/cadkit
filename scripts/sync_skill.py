#!/usr/bin/env python3
"""Build standalone agent references independently of the human documentation."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "skill" / "references"
AGENT_SOURCES = ROOT / "agent-reference"
LINK = re.compile(r"(\[[^\]]*\]\()([^\s)]+)([^)]*\))")


def public_documents() -> list[Path]:
    return sorted(path for path in (ROOT / "docs").rglob("*.md") if not path.name.endswith(".local.md"))


def reference_path(source: Path) -> Path:
    if source.is_relative_to(AGENT_SOURCES):
        return REFERENCES / source.relative_to(AGENT_SOURCES)
    if source == ROOT / "desktop" / "README.md":
        return REFERENCES / "desktop.md"
    return REFERENCES / source.relative_to(ROOT)


def generated_references() -> dict[Path, bytes]:
    """Copy agent guidance and its local link targets into a standalone skill."""
    pending = [*sorted(AGENT_SOURCES.glob("*.md")), ROOT / "desktop" / "README.md"]
    generated: dict[Path, bytes] = {}
    while pending:
        source = pending.pop()
        destination = reference_path(source)
        if destination in generated:
            continue
        if source.suffix != ".md":
            generated[destination] = source.read_bytes()
            continue

        def rewrite(match: re.Match[str]) -> str:
            url = urlsplit(match[2])
            if url.scheme or url.netloc or not url.path or url.path.startswith("/"):
                return match[0]
            target = (source.parent / unquote(url.path)).resolve()
            # The desktop README links to human guides. Keep the installed skill
            # self-contained with its task-oriented equivalents, and link other
            # human pages to the published book rather than copying autodoc markup.
            equivalents = {
                ROOT / "docs/how-to/install.md": AGENT_SOURCES / "install.md",
                ROOT / "docs/reference/mechanics.md": AGENT_SOURCES / "mechanics.md",
            }
            target = equivalents.get(target, target)
            if not target.is_relative_to(ROOT) or not target.is_file() or target.name.endswith(".local.md"):
                raise ValueError(f"Unpublishable documentation link in {source.relative_to(ROOT)}: {match[2]}")
            if target.is_relative_to(ROOT / "docs"):
                page = target.relative_to(ROOT / "docs").with_suffix("").as_posix()
                if page == "index":
                    page = ""
                elif page.endswith("/index"):
                    page = page[:-6]
                published = "https://aurkakoak.github.io/cadkit/docs/" + (f"{page}/" if page else "")
                if url.fragment:
                    published += f"#{url.fragment}"
                return match[1] + published + match[3]
            pending.append(target)
            relative = Path(os.path.relpath(reference_path(target), destination.parent)).as_posix()
            if url.query:
                relative += f"?{url.query}"
            if url.fragment:
                relative += f"#{url.fragment}"
            return match[1] + relative + match[3]

        generated[destination] = LINK.sub(rewrite, source.read_text(encoding="utf-8")).encode("utf-8")
    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if committed references need regeneration.")
    args = parser.parse_args()
    expected = generated_references()
    entrypoint = ROOT / "skill" / "SKILL.md"
    for match in LINK.finditer(entrypoint.read_text(encoding="utf-8")):
        url = urlsplit(match[2])
        if url.scheme or url.netloc or not url.path:
            continue
        target = (entrypoint.parent / unquote(url.path)).resolve()
        if not target.is_relative_to(entrypoint.parent) or (target not in expected and not target.is_file()):
            raise ValueError(f"Broken skill entrypoint link: {match[2]}")
    existing = set(REFERENCES.rglob("*")) if REFERENCES.exists() else set()
    stale = sorted(
        path for path in existing
        if path.is_file() and path not in expected
        and "__pycache__" not in path.relative_to(REFERENCES).parts
        and path.suffix not in (".pyc", ".pyo")
    )
    changed = sorted(path for path, content in expected.items() if not path.exists() or path.read_bytes() != content)
    if args.check:
        for path in changed + stale:
            print(f"Out of sync: {path.relative_to(ROOT)}")
        if changed or stale:
            print("Run python scripts/sync_skill.py and commit the updated references.")
            return 1
        print(f"Skill references are current ({len(expected)} files).")
        return 0
    for path in stale:
        path.unlink()
    for path in changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected[path])
    print(f"Synced {len(expected)} skill reference files ({len(changed)} updated).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
