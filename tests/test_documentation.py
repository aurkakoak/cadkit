"""Distribution boundaries for the human book and the standalone agent skill."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_trial_tutorial_includes_expand_sections_and_collapsible_complete_files(tmp_path):
    trial = load_script("build_trial")
    write(tmp_path, "examples/tutorial/model.py", (
        '"""Complete model."""\n'
        'def body():\n'
        '    # --8<-- [start:pads]\n'
        '    pads = make_pads()\n'
        '    return pads\n'
        '    # --8<-- [end:pads]\n'
    ))
    page = ('```python\n--8<-- "examples/tutorial/model.py:pads"\n```\n\n'
            '??? example "Complete example"\n\n'
            '    ```python\n    --8<-- "examples/tutorial/model.py"\n    ```\n')
    expanded = trial.expand_tutorial_examples(page, tmp_path)
    assert '```python\npads = make_pads()\nreturn pads\n```' in expanded
    assert '    def body():\n        pads = make_pads()' in expanded
    assert '--8<--' not in expanded
    with pytest.raises(ValueError, match="Missing or unclosed"):
        trial.expand_tutorial_examples('--8<-- "examples/tutorial/model.py:missing"', tmp_path)


def load_script(name):
    specification = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def write(root, relative, content):
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        destination.write_bytes(content)
    else:
        destination.write_text(content)
    return destination


@pytest.fixture
def documentation_tools(tmp_path, monkeypatch):
    references = load_script("sync_skill")
    monkeypatch.setattr(references, "ROOT", tmp_path)
    monkeypatch.setattr(references, "REFERENCES", tmp_path / "skill/references")
    monkeypatch.setattr(references, "AGENT_SOURCES", tmp_path / "agent-reference")
    monkeypatch.setitem(sys.modules, "sync_skill", references)
    site = load_script("build_site")
    write(tmp_path, "site/assets/mark.svg", "<svg/>")
    return references, site


def test_nested_human_pages_keep_local_links_and_images_but_link_code_to_source(documentation_tools, tmp_path):
    references, site = documentation_tools
    write(tmp_path, "docs/tutorials/start.md", (
        "# Tutorial\n\n[Next task](../how-to/export.md#output)\n"
        "![Actual model](../assets/tutorial/box.png)\n"
        "[Complete example](../../examples/tutorial/01_box.py#L5)\n"
        '```python\n--8<-- "examples/tutorial/01_box.py"\n```\n'
    ))
    write(tmp_path, "docs/how-to/export.md", "# Export\n\n## Output\n")
    write(tmp_path, "docs/assets/tutorial/box.png", b"screenshot contents")
    write(tmp_path, "examples/tutorial/01_box.py", "def box(): return 1\n")
    write(tmp_path, "docs/tutorials/notes.local.md", "Private working draft")
    write(tmp_path, "agent-reference/agent-guide.md", "Agent-only instructions")

    site.prepare_documentation()

    staged = site.STAGING / "tutorials/start.md"
    content = staged.read_text()
    assert "[Next task](../how-to/export.md#output)" in content
    assert "![Actual model](../assets/tutorial/box.png)" in content
    assert "https://github.com/aurkakoak/cadkit/blob/main/examples/tutorial/01_box.py#L5" in content
    assert (site.STAGING / "assets/tutorial/box.png").read_bytes() == b"screenshot contents"
    assert (site.STAGING / "assets/mark.svg").read_text() == "<svg/>"
    assert not (site.STAGING / "tutorials/notes.local.md").exists()
    assert not (site.STAGING / "agent-guide.md").exists()
    assert [p.relative_to(tmp_path / "docs").as_posix() for p in references.public_documents()] == [
        "how-to/export.md", "tutorials/start.md",
    ]
    # Rewriting cannot leave a source-tree-relative link that breaks after staging.
    for match in references.LINK.finditer(content):
        url = urlsplit(match[2])
        if not url.scheme:
            assert (staged.parent / unquote(url.path)).is_file()


@pytest.mark.parametrize("target", ["missing.md", "notes.local.md"])
def test_staging_rejects_missing_pages_and_private_drafts(documentation_tools, tmp_path, target):
    _, site = documentation_tools
    write(tmp_path, "docs/tutorials/start.md", f"[Broken destination]({target})\n")
    write(tmp_path, "docs/tutorials/notes.local.md", "Private working draft")
    with pytest.raises(ValueError, match="Broken documentation link"):
        site.prepare_documentation()


def test_skill_stays_self_contained_without_copying_human_autodoc_pages(documentation_tools, tmp_path):
    references, _ = documentation_tools
    write(tmp_path, "agent-reference/agent-guide.md", (
        "# Agent instructions\n"
        "[Local workflow](tasks/model.md)\n"
        "[Runnable example](../examples/tutorial/01_box.py)\n"
        "[Human API reference](../docs/reference/project.md#cadkit.Project)\n"
    ))
    write(tmp_path, "agent-reference/tasks/model.md", "# Follow the active project\n")
    write(tmp_path, "agent-reference/install.md", "# Agent installation instructions\n")
    write(tmp_path, "agent-reference/mechanics.md", "# Agent mechanical checks\n")
    write(tmp_path, "desktop/README.md", (
        "# Desktop\n"
        "[Install](../docs/how-to/install.md)\n"
        "[Mechanics](../docs/reference/mechanics.md)\n"
    ))
    write(tmp_path, "examples/tutorial/01_box.py", "def box(): return 1\n")
    write(tmp_path, "docs/reference/project.md", "# API\n\n::: cadkit.Project\n")
    write(tmp_path, "docs/how-to/install.md", "# Human installation tutorial\n")
    write(tmp_path, "docs/reference/mechanics.md", "# Human mechanical reference\n")

    generated = references.generated_references()
    relative = {path.relative_to(references.REFERENCES).as_posix(): data for path, data in generated.items()}
    assert set(relative) == {
        "agent-guide.md", "tasks/model.md", "install.md", "mechanics.md", "desktop.md",
        "examples/tutorial/01_box.py",
    }
    assert relative["examples/tutorial/01_box.py"] == b"def box(): return 1\n"
    assert b"https://aurkakoak.github.io/cadkit/docs/reference/project/#cadkit.Project" in relative["agent-guide.md"]
    assert b"[Install](install.md)" in relative["desktop.md"]
    assert b"[Mechanics](mechanics.md)" in relative["desktop.md"]
    assert not any(b"::: cadkit.Project" in content for content in relative.values())
    for source, content in generated.items():
        if source.suffix != ".md":
            continue
        for match in references.LINK.finditer(content.decode()):
            url = urlsplit(match[2])
            if not url.scheme:
                assert (source.parent / unquote(url.path)).resolve() in generated
