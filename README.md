# Highlander Experiment Harness

Experiment harness for the paper "Workload-Aware Deployment Pattern Selection for Cloud-Native Commerce Systems" (Highlander).

## Quick Start

### Prerequisites

- Python 3.11+
- Docker
- kubectl
- kind (for kind platform)
- 8 vCPU, 16 GB RAM, 30 GB free disk (for kind platform)

### Setup

```bash
# Install dependencies
pip install -e .

# Or with uv (recommended)
uv pip install -e .
```

### Environment Check

```bash
make env-check
```

### Testing

```bash
# Run protocol and unit tests
make test
```

### Running Experiments

#### Local Platform (fast iteration)

```bash
# Smoke test (1 trial per Series A condition)
make smoke PLATFORM=local

# Pilot run (3 trials per cell)
make pilot PLATFORM=local SERIES=A
```

#### Kind Platform (paper testbed)

```bash
# Start cluster
make cluster-up PLATFORM=kind

# Smoke test
make smoke PLATFORM=kind

# Pilot run
make pilot PLATFORM=kind SERIES=A

# Stop cluster
make cluster-down PLATFORM=kind
```

### Analysis

```bash
# Generate tables and figures from raw data
make analyze
```

## Documentation

- `RUNBOOK.md` - Detailed runbook with host requirements, runtimes, and troubleshooting
- `docs/PROTOCOL.md` - SQL semantics, state machine, and fault semantics
- `docs/PAPER_METHODS.md` - Code behavior description for paper Section V-A/B
- `docs/DATA_DICTIONARY.md` - Raw file and column documentation

## Project Structure

```
highlander-harness/
  sql/            # PostgreSQL schema and functions
  worker/         # Worker implementation (Python)
  runner/         # Experiment runner and series logic
  helper/         # Helper container scripts (kind platform)
  httpsvc/        # HTTP service for Series F/G (Go)
  loadgen/        # Load generator for Series F/G
  k8s/            # Kubernetes manifests
  analysis/       # Analysis code (tables, figures, statistics)
  tests/          # Protocol and unit tests
  docs/           # Documentation
  data/           # Raw experiment outputs (gitignored)
```

## License

Apache-2.0 - see LICENSE file

## Citation

If you use this software, please cite it as described in CITATION.cff.
