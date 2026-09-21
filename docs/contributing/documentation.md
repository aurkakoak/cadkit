# Write and check documentation

The human documentation follows [Diátaxis](https://diataxis.fr/): a tutorial
teaches by doing, a how-to guide answers a particular task, an explanation
develops understanding, and reference describes the implemented interface.
Choose the reader's need before choosing a page location.

## Build and preview

From a checkout with uv installed:

```sh
uv run --locked --only-group docs python scripts/build_site.py
uv run --locked --only-group docs mkdocs serve
```

The build stages nested Markdown and assets in `build/docs-source`, validates
links, and writes the complete Pages site to `build/site`. The API generator
reads Python source without importing the CAD kernel. To keep a separate
existing modelling environment intact, set `UV_PROJECT_ENVIRONMENT` to a
different directory for these commands.

After changing Markdown, stage it again before refreshing the preview:

```sh
uv run --locked --only-group docs python scripts/build_site.py --prepare-only
```

## Keep the tutorial executable

Each tutorial chapter maps to a complete file in
[`examples/tutorial`](../../examples/tutorial/README.md). Include executable
code from these files with `pymdownx.snippets`, rather than maintaining a second
copy in Markdown. Give each step an observable result and link the final
chapter to the relevant how-to guides.

Screenshots in `docs/assets/tutorial/` show the running desktop app with these
examples. Update them when the instructions or relevant UI changes. Run the
tutorial regression tests after changing examples:

```sh
uv run --locked --extra desktop pytest tests/test_tutorial.py -q
```

## Keep reference tied to the implementation

The [mkdocstrings Python handler](https://mkdocstrings.github.io/python/)
generates signatures, types, defaults and documentation from `src/cadkit`.
Reference pages select public objects with `:::` directives and add short
context around them. Document parameters, units, return values and constraints
in the source docstrings. Use Google-style `Args:`, `Returns:` and `Raises:`
sections where they clarify the interface. Do not claim validation or inferred
behaviour that the implementation does not provide.

Add a new public symbol to the appropriate reference page and navigation. Use
cross-references to the canonical object instead of rendering it twice.
The strict build rejects broken page links and unresolved object references.

## Keep agent guidance separate

`agent-reference/` holds concise operational guidance for the agent skill.
`scripts/sync_skill.py` assembles it into the standalone `skill/references/`
directory. Human tutorials and generated API pages are not copied into the
skill. After editing agent guidance, run:

```sh
python scripts/sync_skill.py
python scripts/sync_skill.py --check
```

When moving a published page, add a redirect in `mkdocs.yml` so existing links
continue to work. The obsolete design proposal is intentionally not redirected
or republished.
