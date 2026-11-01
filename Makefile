# napkin2factory developer entry points (GRAND_PLAN §8.2).
# `make check` is the full gate, run on main's tip in the primary folder before a push (CI
# repeats it); it grows by milestone. Tasks: `make task`, `make land`, `make tasks`,
# `make abandon` (scripts/task.sh).
# `make check-full` adds the kiln (and its napkin stage), the three demos, and the timing
# assertions (N2F_TIMING=1). `make check-fast` is the land gate (S-131): lint, types and the
# unit and smoke tests, no end-to-end, no examples, no coverage floor.

UV ?= uv
PY := $(UV) run
EXAMPLES_FAST := examples/bracket examples/enclosure

.PHONY: check check-fast check-full lint types unit golden templates goldens todo-grep examples-fast kiln demos verify-list clean \
	task land tasks abandon

check: lint types unit golden examples-fast todo-grep

# The default `make land` gate (S-131, FOUNDATION §6): what a task can break in a minute or
# three. The end-to-end tests, the goldens, the examples and the coverage floor stay in
# `make check`, run on main before a push and by CI.
check-fast: lint types todo-grep
	$(PY) pytest tests/smoke tests/unit -m "not full" $(XDIST) -q

lint:
	$(PY) ruff check src tests scripts examples
	$(PY) ruff format --check src tests scripts examples

types:
	$(PY) mypy src/napkin2factory/core src/napkin2factory/calckit

export N2F_OFFLINE ?= 1

# Parallel test runs (pytest-xdist). One worker per core; `--dist loadfile` keeps a module's
# shared product build on one worker. `make check XDIST=` runs serially; the timing tests in
# check-full stay serial because they measure wall-clock.
XDIST ?= -n auto --dist loadfile

unit:
	$(PY) pytest tests/smoke tests/unit tests/e2e -m "not full" $(XDIST) --cov=napkin2factory.core --cov=napkin2factory.calckit --cov-report=term-missing:skip-covered --cov-fail-under=80

golden:
	$(PY) pytest tests/golden $(XDIST)

examples-fast:
	@for ex in $(EXAMPLES_FAST); do \
	  if [ -d $$ex ]; then \
	    echo "== $$ex"; \
	    (cd $$ex && $(PY) n2f validate && $(PY) n2f lint && $(PY) n2f build && $(PY) n2f check) || exit 1; \
	    $(PY) python tests/validate_outputs.py $$ex || exit 1; \
	  fi; \
	done

check-full: check kiln demos
	N2F_TIMING=1 $(PY) pytest tests/e2e/test_timing.py tests/e2e/test_concept_build.py -q

# The kiln's concept cards are rebuilt in a scratch copy (build/kiln-napkin). An unchanged card
# no longer changes on a rebuild (its screening time moves only with its content, S-086), but a
# card whose screening is stale would be rewritten in place: `make` would leave the tree dirty
# and test_kiln.py would then compare the rebuilt cards with themselves. In the copy, a stale
# shipped card fails that test instead. Every card is built, rejected ones too, so the board
# shows the whole story with pictures.
KILN_NAPKIN := build/kiln-napkin

kiln:
	@echo "== examples/kiln"
	cd examples/kiln && $(PY) n2f validate && $(PY) n2f lint && $(PY) n2f build && $(PY) n2f check
	$(PY) python tests/validate_outputs.py examples/kiln
	@echo "== examples/kiln: the napkin stage (concepts, board)"
	rm -rf $(KILN_NAPKIN) && mkdir -p build && cp -R examples/kiln $(KILN_NAPKIN) && rm -rf $(KILN_NAPKIN)/build
	cd $(KILN_NAPKIN) && $(PY) n2f concept lint && $(PY) n2f concept build --all && \
	  $(PY) n2f concept board
	$(PY) python tests/validate_outputs.py $(KILN_NAPKIN) --stage concepts
	N2F_TIMING=1 $(PY) pytest tests/e2e/test_kiln.py -q

# The three demos share nothing (own temp copy each), so they run side by side; they are one
# file, so the default distribution, not --dist loadfile, spreads them (S-079).
demos:  # demo.sh, demo-design.sh and demo-napkin.sh, each in a temp copy (D23)
	N2F_TIMING=1 $(PY) pytest tests/e2e/test_demos.py -q -n 3

templates:
	$(PY) python -m napkin2factory.templates.sync

goldens:
	@test -n "$(REASON)" || (echo "make goldens REASON='why'" && exit 1)
	N2F_UPDATE_GOLDENS=1 $(PY) pytest tests/golden -q
	@echo "goldens regenerated: $(REASON)" >> tests/golden/REGENERATION_LOG.md

todo-grep:
	@! grep -rnE "TODO|FIXME" src/ --include=*.py --include=*.js --include=*.yaml --include=*.md --include=*.html --include=*.j2 \
	  --exclude-dir=vendor | grep -vE "B-[0-9]{4}" || (echo "TODO/FIXME without a BACKLOG id" && exit 1)

verify-list:  # every engineering number still to be confirmed, as Markdown
	@$(PY) python scripts/verify_list.py

clean:
	rm -rf build dist examples/*/build .pytest_cache .mypy_cache .ruff_cache

# One trunk, a folder per task (scripts/task.sh). `make task NAME=<slug> GOAL="<one line>"` in
# the primary folder; `make land` inside the task folder (its gate is `make check-fast`;
# `LAND_GATE=check` runs make check instead); `make tasks` lists open work, left by any agent;
# `make abandon NAME=<slug> CONFIRM=1` drops a task.
task:
	@sh scripts/task.sh new "$(NAME)" "$(GOAL)"

land:
	@sh scripts/task.sh land

tasks:
	@sh scripts/task.sh list

abandon:
	@CONFIRM="$(CONFIRM)" sh scripts/task.sh abandon "$(NAME)"
