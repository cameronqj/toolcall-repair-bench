.PHONY: help install dev test lint validate score leaderboard leaderboard-check capture-ollama clean

help:
	@echo "toolcall-repair-bench — make targets:"
	@echo "  install        pip install -e ."
	@echo "  dev            pip install -e \".[dev]\""
	@echo "  test           run the test suite"
	@echo "  lint           run ruff"
	@echo "  validate       validate the corpus against the schema"
	@echo "  score          run the deterministic scorer (JSON to stdout)"
	@echo "  leaderboard    regenerate the README leaderboard and results.json"
	@echo "  leaderboard-check  verify the committed leaderboard is in sync (CI gate)"
	@echo "  capture-ollama scaffold a PENDING captured case from a raw output file"
	@echo "  clean          remove caches and build artifacts"

install:
	python3 -m pip install -e .

dev:
	python3 -m pip install -e ".[dev]"

test:
	python3 -m pytest

lint:
	python3 -m ruff check .

validate:
	python3 -m tcrb.schema_validate

score:
	python3 -m tcrb.scorer

leaderboard:
	python3 -m tcrb.leaderboard

# Fail if the committed README table / results.json are out of sync. CI-safe:
# adapters scored in results.json but unavailable here (e.g. local_tool_proxy)
# are skipped, but README<->results.json consistency is always enforced.
leaderboard-check:
	python3 -m tcrb.leaderboard --check

# Scaffold a pending captured case from an already-captured raw output file.
# No network, no API key. Example:
#   make capture-ollama ID=0042-qwen-fenced RAW=out.txt MODEL=qwen2.5-coder:7b
capture-ollama:
	@test -n "$(ID)"    || { echo "set ID=<case-id>"; exit 2; }
	@test -n "$(RAW)"   || { echo "set RAW=<raw-output-file or ->"; exit 2; }
	@test -n "$(MODEL)" || { echo "set MODEL=<model>"; exit 2; }
	python3 -m tcrb.capture --id "$(ID)" --raw "$(RAW)" --model "$(MODEL)" \
		--runtime "$(or $(RUNTIME),ollama)" --harness "$(or $(HARNESS),openai-compatible)"

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .coverage .tox
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
