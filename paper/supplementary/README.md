# Exploratory transactional interleaving study

These are **measured outputs from a controlled, serialized SQLite experiment**, not outputs from the planned Kubernetes/PostgreSQL campaign. The experiment executes actual SQL transactions in `sqlite3` and imposes event order. It does not create concurrent Pods, SIGSTOP faults, live lease expiry, HTTP load, realistic CPU work, or remote network partitions. Its results test the sink rules within the model and cannot estimate deployment speed, downtime, resource cost, production reliability, or failure incidence.

Reproduce from the repository root:

```bash
python3 -m unittest tests.test_exploratory_sqlite -v
python3 -m analysis.exploratory_sqlite --output paper/supplementary
```

Requires Python 3.11+ and NumPy. For each condition, the ordered and duplicate experiments run 30 trials of 100 keys. The ordered experiment schedules a successor first on a seeded 70% of keys and tests a lower-version former worker; all conditions share the same trial seed. After-grant cells use event time, with successor write at 2 s and old worker at 0, 1, or 5 s. The replay experiment draws 5% lost acknowledgments from 100 accepted calls per trial, waits 50 ms before each retry, and compares the same op-key response; its draws are paired across C2f, C3, C4. The runner preserves 720 raw trial rows and 43 metric summary rows. All cells have 30 valid, zero invalid trials by construction. Trial-level means have 10,000-resample percentile bootstrap 95% intervals with seed 2026. Zero-count intervals are not offered as safety guarantees because attempts within each trial share a schedule and sink state.

`sqlite_trials.csv` contains one row per condition/series/trial; `sqlite_summary.csv` contains separate metric totals, means and bootstrap intervals. The production campaign remains unrun; tables and figure placeholders in the manuscript remain unfilled for that campaign.
