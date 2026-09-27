# Exploratory transactional interleaving study

These CSVs are **outputs of a scripted SQLite sink-rule model**, not the PostgreSQL implementation or the planned Kubernetes campaign. A caller supplies a scheduled holder and epoch; the program applies a corresponding rule in an SQLite transaction. It does not run `own.acquire`, `own.renew`, `sink.*`, `rsink.*`, concurrent Pods, SIGSTOP faults, live lease expiry, HTTP load, provider calls, or remote network partitions. The counts describe these input schedules and rules; they are not failure-rate estimates or evidence of deployment speed, downtime, resource cost, or production reliability.

From the repository root:

```bash
python3 -m unittest tests.test_exploratory_sqlite -v
python3 -m analysis.exploratory_sqlite --output paper/supplementary
python3 -m analysis.plot_exploratory
python3 -m analysis.render_sqlite_results
```

`experiment_config.json` records the schedule inputs. Before every ordered trial, the former writer publishes v1 for every feed item. The former worker then delays v2 while the successor publishes v3. Within each of 30 seeded ordered schedules, key order is shuffled and the successor writes first for each key with input probability 0.7. Conditions share each trial's sampled schedule. The C3r remote epoch is one value for the entire feed; it advances when the successor's first epoch-2 write reaches that sink, regardless of item key.

The pause duplicate condition has **one scheduled run** per applicable condition (100 keys), with a former epoch-1 writer resubmitting after takeover. The lost-ack condition has 30 paired seeded schedules per condition, with 100 initial calls, an input loss probability of 0.05, and an actual 50 ms wait before a current-owner retry. The after-grant sweep has one deterministic scheduled run per condition and delay; event time places the successor's first write at 2 s and old-worker resumption at 0, 1, or 5 s. The entire former batch is released before the entire successor batch for a delay below 2 s; their order reverses above 2 s. These are imposed event-time schedules, not wall-clock latency measurements. The single-run cells are not repeated to create artificial trial counts.

`sqlite_trials.csv` contains 343 rows, one for each scheduled run; `sqlite_summary.csv` contains outcome totals without confidence intervals. `analysis/render_sqlite_results.py` derives the paper's observed tables and study parameters from these files. No bootstrap interval or failure-rate bound is inferred from probabilities chosen as simulation inputs. The full PostgreSQL/kind campaign remains unrun.
