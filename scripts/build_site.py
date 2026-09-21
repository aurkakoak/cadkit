#!/usr/bin/env python3
"""Build the landing page, installers and Material docs as one Pages artifact."""

from __future__ import annotations

import argparse
import re
import shutil
from urllib.parse import unquote, urlsplit

from sync_skill import LINK, ROOT, public_documents


REPOSITORY = "https://github.com/aurkakoak/cadkit"
STAGING = ROOT / "build" / "docs-source"
OUTPUT = ROOT / "build" / "site"


def prepare_documentation() -> None:
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    documents = {source: source.name for source in public_documents()}
    documents[ROOT / "desktop" / "README.md"] = "desktop.md"
    for source, name in documents.items():
        def rewrite(match: re.Match[str]) -> str:
            url = urlsplit(match[2])
            if url.scheme or url.netloc or not url.path or url.path.startswith("/"):
                return match[0]
            target = (source.parent / unquote(url.path)).resolve()
            if target in documents:
                destination = documents[target]
            elif target.is_file() and target.is_relative_to(ROOT / "docs" / "assets"):
                destination = target.relative_to(ROOT / "docs").as_posix()
            elif target.is_file() and target.is_relative_to(ROOT) and not target.name.endswith(".local.md"):
                destination = f"{REPOSITORY}/blob/main/{target.relative_to(ROOT).as_posix()}"
            else:
                raise ValueError(f"Broken documentation link in {source.relative_to(ROOT)}: {match[2]}")
            if url.query:
                destination += f"?{url.query}"
            if url.fragment:
                destination += f"#{url.fragment}"
            return match[1] + destination + match[3]

        (STAGING / name).write_text(LINK.sub(rewrite, source.read_text(encoding="utf-8")), encoding="utf-8")
    shutil.copytree(ROOT / "site" / "assets", STAGING / "assets")
    if (ROOT / "docs" / "assets").exists():
        shutil.copytree(ROOT / "docs" / "assets", STAGING / "assets", dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true", help="Stage docs for mkdocs serve without building.")
    args = parser.parse_args()
    prepare_documentation()
    if args.prepare_only:
        print(f"Prepared {STAGING}; run mkdocs serve to preview documentation.")
        return

    # All output is derived; preserve the separately staged canonical docs.
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(ROOT / "site", OUTPUT)
    shutil.copy2(ROOT / "scripts" / "install.sh", OUTPUT / "install.sh")
    (OUTPUT / ".nojekyll").touch()
    from mkdocs.commands.build import build
    from mkdocs.config import load_config

    config = load_config(str(ROOT / "mkdocs.yml"), strict=True)
    build(config)
    print(f"Built landing page and documentation: {OUTPUT}")


if __name__ == "__main__":
    main()
