# napkin2factory developer entry points (GRAND_PLAN §8.2).
# `make check` is the fast gate run before every commit; it grows by milestone.
# `make check-full` adds the kiln, both demos, and the timing assertions (N2F_TIMING=1).

UV ?= uv
PY := $(UV) run
EXAMPLES_FAST := examples/bracket examples/enclosure

.PHONY: check check-full lint types unit golden templates goldens todo-grep examples-fast kiln demos clean

check: lint types unit golden examples-fast todo-grep

lint:
	$(PY) ruff check src tests
	$(PY) ruff format --check src tests

types:
	$(PY) mypy src/napkin2factory/core

export N2F_OFFLINE ?= 1

unit:
	$(PY) pytest tests/smoke tests/unit tests/e2e -m "not full" --cov=napkin2factory.core --cov-report=term-missing:skip-covered --cov-fail-under=80

golden:
	$(PY) pytest tests/golden

examples-fast:
	@for ex in $(EXAMPLES_FAST); do \
	  if [ -d $$ex ]; then \
	    echo "== $$ex"; \
	    (cd $$ex && $(PY) n2f validate && $(PY) n2f lint && $(PY) n2f build && $(PY) n2f check) || exit 1; \
	    $(PY) python tests/validate_outputs.py $$ex || exit 1; \
	  fi; \
	done

check-full: check kiln demos
	N2F_TIMING=1 $(PY) pytest tests/e2e/test_timing.py -q

kiln:
	@echo "== examples/kiln"
	cd examples/kiln && $(PY) n2f validate && $(PY) n2f lint && $(PY) n2f build && $(PY) n2f check
	$(PY) python tests/validate_outputs.py examples/kiln
	N2F_TIMING=1 $(PY) pytest tests/e2e/test_kiln.py -q

demos:
	N2F_TIMING=1 $(PY) pytest tests/e2e/test_demos.py -q

templates:
	$(PY) python -m napkin2factory.templates.sync

goldens:
	@test -n "$(REASON)" || (echo "make goldens REASON='why'" && exit 1)
	N2F_UPDATE_GOLDENS=1 $(PY) pytest tests/golden -q
	@echo "goldens regenerated: $(REASON)" >> tests/golden/REGENERATION_LOG.md

todo-grep:
	@! grep -rnE "TODO|FIXME" src/ --include=*.py --include=*.js --include=*.yaml --include=*.md --include=*.html --include=*.j2 \
	  --exclude-dir=vendor | grep -vE "B-[0-9]{4}" || (echo "TODO/FIXME without a BACKLOG id" && exit 1)

clean:
	rm -rf build dist examples/*/build .pytest_cache .mypy_cache .ruff_cache
