# Highlander Experiment Harness

Experiment harness for the paper "Workload-Aware Deployment Pattern Selection for Cloud-Native Commerce Systems" (Highlander).

The seven-page IEEE conference manuscript source is in [`paper/manuscript.tex`](paper/manuscript.tex); its figures and references are in the same directory. The paper includes a scripted SQLite sink-rule study with [raw schedules, summary counts and scope notes](paper/supplementary/README.md). These counts are not failure-rate estimates. The planned Kubernetes/PostgreSQL campaign remains unrun.

The [v8 change log](docs/REVISION_V8.md) and [v8 numeric audit](docs/V8_NUMBER_AUDIT.md) document the corrected after-grant batch schedule and its figure results.

**Implementation status:** The runner, Series C after-grant delay, replay classification, and Series F/G service/load generation are incomplete. The commands below describe the intended interface and are not evidence that a full campaign succeeds. The analysis report entry point and several referenced files are still missing.

Reproduce the limited SQLite mechanism study without a cluster:

```bash
python3 -m unittest tests.test_exploratory_sqlite -v
python3 -m analysis.exploratory_sqlite --output paper/supplementary
python3 -m analysis.plot_exploratory
python3 -m analysis.render_sqlite_results --old-ref 32e07037bb6a8f8d372e474222b8d5e140a32d12
python3 -m analysis.render_sqlite_results --v8-ref 7468239
```

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

- `docs/PROTOCOL.md` - SQL semantics, state machine, and fault semantics
- `docs/DATA_DICTIONARY.md` - Raw file and column documentation

## Project Structure

```
highlander-harness/
  sql/            # PostgreSQL schema and functions
  worker/         # Worker implementation (Python)
  runner/         # Experiment runner and series logic
  helper/         # Helper container scripts (kind platform)
  paper/          # IEEE manuscript source and figures
  k8s/            # Kubernetes manifests
  analysis/       # Analysis code (tables, figures, statistics)
  tests/          # Protocol and unit tests
  docs/           # Documentation
  data/           # Planned raw experiment outputs (gitignored)
```

## License

Apache-2.0 - see LICENSE file

## Citation

If you use this software, please cite it as described in CITATION.cff.

## Measured PostgreSQL scheduled results

The IEEE manuscript and primary raw SQL schedules are in `paper/`. The PostgreSQL 16.15 CI run completed 343 scheduled rows and 53 passing tests; it compares to the SQLite rule model with zero per-cell metric mismatches. Regenerate results with `python3 -m analysis.render_sqlite_results --source pg` and `python3 -m analysis.plot_exploratory --source pg`, then compile `paper/manuscript.tex`. The CI run is https://github.com/nallabothukoteswar-wq/highlander-harness/actions/runs/36291161498 . This experiment does not measure Kubernetes downtime, cost, or throughput.
