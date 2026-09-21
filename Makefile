UV ?= uv
.PHONY: setup test example build docs docs-build

setup:
	$(UV) sync --locked --extra desktop

test:
	$(UV) run --locked --extra desktop pytest tests -q

example:
	PYTHONPATH=examples $(UV) run --locked cadkit --project bracket:PROJECT build all
	PYTHONPATH=examples $(UV) run --locked cadkit --project bracket:PROJECT check

build:
	$(UV) build

docs:
	$(UV) run --locked --only-group docs python scripts/build_site.py --prepare-only
	$(UV) run --locked --only-group docs mkdocs serve

docs-build:
	$(UV) run --locked --only-group docs python scripts/build_site.py
