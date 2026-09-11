PYTHON ?= .venv/bin/python
.PHONY: test example

test:
	$(PYTHON) -m pytest tests -q

example:
	PYTHONPATH=examples $(PYTHON) -m cadkit.cli --project bracket:PROJECT build all
	PYTHONPATH=examples $(PYTHON) -m cadkit.cli --project bracket:PROJECT check
