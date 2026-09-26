.PHONY: help env-check cluster-up cluster-down test smoke pilot campaign analyze clean

PLATFORM ?= local
SERIES ?= all

help:
	@echo "Highlander Harness Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  make env-check        - Check environment requirements"
	@echo "  make cluster-up       - Start kind cluster (PLATFORM=kind)"
	@echo "  make cluster-down     - Stop kind cluster"
	@echo "  make test             - Run protocol and unit tests"
	@echo "  make smoke            - Run smoke test (1 trial per Series A condition)"
	@echo "  make pilot            - Run pilot (3 trials per cell)"
	@echo "  make campaign         - Run full campaign (all trials)"
	@echo "  make analyze          - Generate analysis outputs"
	@echo "  make clean            - Clean build artifacts and data"
	@echo ""
	@echo "Variables:"
	@echo "  PLATFORM=local|kind   - Target platform (default: local)"
	@echo "  SERIES=all|A|B|...    - Series to run (default: all)"

env-check:
	@echo "Checking environment..."
	@which python3 || (echo "python3 not found" && exit 1)
	@python3 --version | grep -q "3\.1[1-9]" || (echo "Python 3.11+ required" && exit 1)
	@which docker || (echo "docker not found" && exit 1)
	@which kubectl || (echo "kubectl not found" && exit 1)
	@if [ "$(PLATFORM)" = "kind" ]; then \
		which kind || (echo "kind not found (required for PLATFORM=kind)" && exit 1); \
	fi
	@echo "Environment check passed"

cluster-up:
	@if [ "$(PLATFORM)" != "kind" ]; then \
		echo "cluster-up only applies to PLATFORM=kind"; \
		exit 1; \
	fi
	kind create cluster --config k8s/kind-config.yaml
	kubectl apply -f k8s/postgres.yaml
	kubectl wait --for=condition=ready pod -l app=postgres --timeout=300s

cluster-down:
	@if [ "$(PLATFORM)" != "kind" ]; then \
		echo "cluster-down only applies to PLATFORM=kind"; \
		exit 1; \
	fi
	kind delete cluster

test:
	python3 -m pytest tests/ -v

smoke:
	python3 -m runner.cli --platform $(PLATFORM) --series A --trials-per-cell 1 --pilot

pilot:
	python3 -m runner.cli --platform $(PLATFORM) --series $(SERIES) --trials-per-cell 3 --pilot

campaign:
	python3 -m runner.cli --platform $(PLATFORM) --series $(SERIES)

analyze:
	python3 -m analysis.report

clean:
	rm -rf data/
	rm -rf analysis/out/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
